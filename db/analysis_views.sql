-- ============================================================
-- Analysis Views for Fraud Detection and Spending Analysis
-- ============================================================

-- 1. Top 100 organizations by total lifetime spending
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_top_organizations AS
SELECT
    s.billing_npi,
    p.organization_name,
    p.entity_type,
    a.state_code,
    a.city,
    SUM(s.total_paid) AS lifetime_paid,
    SUM(s.total_claims) AS lifetime_claims,
    SUM(s.total_unique_benes) AS lifetime_benes,
    COUNT(DISTINCT s.hcpcs_code) AS distinct_hcpcs,
    MIN(s.claim_month) AS first_claim,
    MAX(s.claim_month) AS last_claim
FROM spending s
JOIN providers p ON p.npi = s.billing_npi AND p.entity_type = 2
LEFT JOIN addresses a ON a.npi = s.billing_npi AND a.address_purpose = 'PRACTICE'
GROUP BY s.billing_npi, p.organization_name, p.entity_type, a.state_code, a.city
ORDER BY lifetime_paid DESC
LIMIT 100;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_top_orgs_npi ON mv_top_organizations(billing_npi);


-- 2. Shared address detection: providers billing from the same address
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_shared_addresses AS
SELECT
    a.street_line_1,
    a.city,
    a.state_code,
    a.zip5,
    COUNT(DISTINCT a.npi) AS provider_count,
    SUM(ss.total_paid) AS combined_spending,
    ARRAY_AGG(DISTINCT a.npi) AS npis
FROM addresses a
JOIN (
    SELECT billing_npi, SUM(total_paid) AS total_paid
    FROM spending
    GROUP BY billing_npi
) ss ON ss.billing_npi = a.npi
WHERE a.address_purpose = 'PRACTICE'
  AND a.street_line_1 IS NOT NULL
GROUP BY a.street_line_1, a.city, a.state_code, a.zip5
HAVING COUNT(DISTINCT a.npi) > 3
ORDER BY combined_spending DESC;

CREATE INDEX IF NOT EXISTS idx_mv_shared_addr_count
    ON mv_shared_addresses(provider_count DESC);


-- 3. Month-over-month spending growth by provider (flag >100% increases)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_spending_growth AS
WITH monthly AS (
    SELECT
        billing_npi,
        claim_month,
        SUM(total_paid) AS monthly_paid
    FROM spending
    GROUP BY billing_npi, claim_month
),
with_lag AS (
    SELECT
        billing_npi,
        claim_month,
        monthly_paid,
        LAG(monthly_paid) OVER (PARTITION BY billing_npi ORDER BY claim_month) AS prev_paid,
        LAG(claim_month) OVER (PARTITION BY billing_npi ORDER BY claim_month) AS prev_month
    FROM monthly
)
SELECT
    w.billing_npi,
    p.organization_name,
    p.last_name,
    p.first_name,
    p.entity_type,
    w.claim_month,
    w.monthly_paid,
    w.prev_paid,
    CASE
        WHEN w.prev_paid > 0
        THEN ROUND(((w.monthly_paid - w.prev_paid) / w.prev_paid * 100)::NUMERIC, 1)
        ELSE NULL
    END AS pct_change
FROM with_lag w
JOIN providers p ON p.npi = w.billing_npi
WHERE w.prev_paid > 0
  AND w.monthly_paid > 10000
  AND ((w.monthly_paid - w.prev_paid) / w.prev_paid * 100) > 100
ORDER BY w.monthly_paid DESC;

CREATE INDEX IF NOT EXISTS idx_mv_growth_npi ON mv_spending_growth(billing_npi);
CREATE INDEX IF NOT EXISTS idx_mv_growth_month ON mv_spending_growth(claim_month);


-- 4. Providers >2 standard deviations above peer mean per HCPCS code
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_outlier_providers AS
WITH hcpcs_stats AS (
    SELECT
        hcpcs_code,
        AVG(total_paid) AS mean_paid,
        STDDEV(total_paid) AS stddev_paid,
        COUNT(*) AS provider_count
    FROM (
        SELECT billing_npi, hcpcs_code, SUM(total_paid) AS total_paid
        FROM spending
        GROUP BY billing_npi, hcpcs_code
    ) per_provider
    GROUP BY hcpcs_code
    HAVING COUNT(*) >= 10
),
provider_hcpcs AS (
    SELECT billing_npi, hcpcs_code, SUM(total_paid) AS total_paid
    FROM spending
    GROUP BY billing_npi, hcpcs_code
)
SELECT
    ph.billing_npi,
    p.organization_name,
    p.last_name,
    p.first_name,
    p.entity_type,
    ph.hcpcs_code,
    h.short_description,
    ph.total_paid AS provider_paid,
    hs.mean_paid AS peer_mean,
    hs.stddev_paid AS peer_stddev,
    ROUND(((ph.total_paid - hs.mean_paid) / NULLIF(hs.stddev_paid, 0))::NUMERIC, 2) AS z_score,
    hs.provider_count AS peer_count
FROM provider_hcpcs ph
JOIN hcpcs_stats hs ON hs.hcpcs_code = ph.hcpcs_code
JOIN providers p ON p.npi = ph.billing_npi
LEFT JOIN hcpcs_codes h ON h.hcpcs_code = ph.hcpcs_code
WHERE hs.stddev_paid > 0
  AND (ph.total_paid - hs.mean_paid) / hs.stddev_paid > 2
ORDER BY (ph.total_paid - hs.mean_paid) / hs.stddev_paid DESC;

CREATE INDEX IF NOT EXISTS idx_mv_outlier_npi ON mv_outlier_providers(billing_npi);
CREATE INDEX IF NOT EXISTS idx_mv_outlier_zscore ON mv_outlier_providers(z_score DESC);


-- 5. Geographic concentration by state and ZIP
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_geographic_concentration AS
SELECT
    a.state_code,
    a.zip5,
    a.city,
    COUNT(DISTINCT s.billing_npi) AS provider_count,
    SUM(s.total_paid) AS total_paid,
    SUM(s.total_claims) AS total_claims,
    SUM(s.total_unique_benes) AS total_benes,
    ROUND((SUM(s.total_paid) / NULLIF(COUNT(DISTINCT s.billing_npi), 0))::NUMERIC, 2)
        AS avg_paid_per_provider
FROM spending s
JOIN addresses a ON a.npi = s.billing_npi AND a.address_purpose = 'PRACTICE'
WHERE a.state_code IS NOT NULL AND a.zip5 IS NOT NULL
GROUP BY a.state_code, a.zip5, a.city
ORDER BY total_paid DESC;

CREATE INDEX IF NOT EXISTS idx_mv_geo_state ON mv_geographic_concentration(state_code);
CREATE INDEX IF NOT EXISTS idx_mv_geo_zip ON mv_geographic_concentration(zip5);
CREATE INDEX IF NOT EXISTS idx_mv_geo_paid ON mv_geographic_concentration(total_paid DESC);


-- 6. Billing vs servicing provider relationship network
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_billing_servicing_network AS
SELECT
    s.billing_npi,
    bp.organization_name AS billing_org,
    bp.last_name AS billing_last,
    bp.entity_type AS billing_type,
    s.servicing_npi,
    sp.organization_name AS servicing_org,
    sp.last_name AS servicing_last,
    sp.entity_type AS servicing_type,
    SUM(s.total_paid) AS total_paid,
    SUM(s.total_claims) AS total_claims,
    COUNT(DISTINCT s.hcpcs_code) AS shared_hcpcs,
    MIN(s.claim_month) AS first_month,
    MAX(s.claim_month) AS last_month
FROM spending s
JOIN providers bp ON bp.npi = s.billing_npi
JOIN providers sp ON sp.npi = s.servicing_npi
WHERE s.billing_npi != s.servicing_npi
GROUP BY s.billing_npi, bp.organization_name, bp.last_name, bp.entity_type,
         s.servicing_npi, sp.organization_name, sp.last_name, sp.entity_type
HAVING SUM(s.total_paid) > 10000
ORDER BY total_paid DESC;

CREATE INDEX IF NOT EXISTS idx_mv_network_billing ON mv_billing_servicing_network(billing_npi);
CREATE INDEX IF NOT EXISTS idx_mv_network_servicing ON mv_billing_servicing_network(servicing_npi);
CREATE INDEX IF NOT EXISTS idx_mv_network_paid ON mv_billing_servicing_network(total_paid DESC);
