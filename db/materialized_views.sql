-- ============================================================
-- Materialized Views for Dashboard Performance
-- ============================================================

-- Provider lifetime summary (joins provider + address info)
CREATE MATERIALIZED VIEW mv_provider_spending_summary AS
SELECT
    s.billing_npi,
    p.entity_type,
    p.organization_name,
    p.last_name,
    p.first_name,
    a.state_code,
    a.city,
    a.zip5,
    COUNT(*) AS total_rows,
    SUM(s.total_claims) AS lifetime_claims,
    SUM(s.total_paid) AS lifetime_paid,
    SUM(s.total_unique_benes) AS lifetime_benes,
    MIN(s.claim_month) AS first_claim_month,
    MAX(s.claim_month) AS last_claim_month,
    COUNT(DISTINCT s.hcpcs_code) AS distinct_hcpcs_codes
FROM spending s
JOIN providers p ON p.npi = s.billing_npi
LEFT JOIN addresses a ON a.npi = s.billing_npi AND a.address_purpose = 'PRACTICE'
GROUP BY s.billing_npi, p.entity_type, p.organization_name,
         p.last_name, p.first_name, a.state_code, a.city, a.zip5;

CREATE UNIQUE INDEX idx_mv_provider_summary ON mv_provider_spending_summary(billing_npi);
CREATE INDEX idx_mv_provider_state ON mv_provider_spending_summary(state_code);
CREATE INDEX idx_mv_provider_paid ON mv_provider_spending_summary(lifetime_paid DESC);


-- Monthly national aggregate
CREATE MATERIALIZED VIEW mv_monthly_spending AS
SELECT
    claim_month,
    COUNT(DISTINCT billing_npi) AS active_providers,
    SUM(total_claims) AS total_claims,
    SUM(total_paid) AS total_paid,
    SUM(total_unique_benes) AS total_benes
FROM spending
GROUP BY claim_month
ORDER BY claim_month;

CREATE UNIQUE INDEX idx_mv_monthly ON mv_monthly_spending(claim_month);


-- State-level aggregate
CREATE MATERIALIZED VIEW mv_state_spending AS
SELECT
    a.state_code,
    SUM(s.total_paid) AS total_paid,
    SUM(s.total_claims) AS total_claims,
    COUNT(DISTINCT s.billing_npi) AS provider_count,
    SUM(s.total_unique_benes) AS total_benes
FROM spending s
JOIN addresses a ON a.npi = s.billing_npi AND a.address_purpose = 'PRACTICE'
GROUP BY a.state_code;

CREATE UNIQUE INDEX idx_mv_state ON mv_state_spending(state_code);


-- Top HCPCS codes
CREATE MATERIALIZED VIEW mv_hcpcs_spending AS
SELECT
    s.hcpcs_code,
    h.short_description,
    SUM(s.total_paid) AS total_paid,
    SUM(s.total_claims) AS total_claims,
    COUNT(DISTINCT s.billing_npi) AS provider_count
FROM spending s
LEFT JOIN hcpcs_codes h ON h.hcpcs_code = s.hcpcs_code
GROUP BY s.hcpcs_code, h.short_description
ORDER BY total_paid DESC;

CREATE UNIQUE INDEX idx_mv_hcpcs ON mv_hcpcs_spending(hcpcs_code);
