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


-- 3. Year-over-year spending growth by provider
--    [EN] Compares annual spending for each provider (individuals & orgs) across consecutive years.
--         No hardcoded % threshold — filtering is done at the application level.
--         Includes authorized official and location data.
--    [RU] Сравнивает годовые расходы каждого поставщика (физ. лица и организации) за последовательные годы.
--         Без жёстко заданного порога % — фильтрация на уровне приложения.
--    [PT] Compara gastos anuais de cada provedor (individuais e organizações) entre anos consecutivos.
--         Sem limite % fixo — filtragem no nível da aplicação.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_spending_growth AS
WITH yearly AS (
    SELECT
        billing_npi,
        EXTRACT(YEAR FROM claim_month)::INT AS claim_year,
        SUM(total_paid) AS annual_paid,
        SUM(total_claims) AS annual_claims,
        SUM(total_unique_benes) AS annual_benes
    FROM spending
    GROUP BY billing_npi, EXTRACT(YEAR FROM claim_month)
),
with_lag AS (
    SELECT
        billing_npi,
        claim_year,
        annual_paid,
        annual_claims,
        annual_benes,
        LAG(annual_paid) OVER (PARTITION BY billing_npi ORDER BY claim_year) AS prev_year_paid,
        LAG(annual_claims) OVER (PARTITION BY billing_npi ORDER BY claim_year) AS prev_year_claims,
        LAG(claim_year) OVER (PARTITION BY billing_npi ORDER BY claim_year) AS prev_year
    FROM yearly
)
SELECT
    w.billing_npi,
    p.organization_name,
    p.last_name,
    p.first_name,
    p.entity_type,
    p.authorized_official_first,
    p.authorized_official_last,
    a.state_code,
    a.city,
    w.claim_year,
    w.prev_year,
    w.annual_paid,
    w.prev_year_paid,
    (w.annual_paid - w.prev_year_paid) AS dollar_change,
    CASE
        WHEN w.prev_year_paid > 0
        THEN ROUND(((w.annual_paid - w.prev_year_paid) / w.prev_year_paid * 100)::NUMERIC, 1)
        ELSE NULL
    END AS pct_change,
    w.annual_claims,
    w.prev_year_claims,
    w.annual_benes
FROM with_lag w
JOIN providers p ON p.npi = w.billing_npi
LEFT JOIN addresses a ON a.npi = w.billing_npi AND a.address_purpose = 'PRACTICE'
WHERE w.prev_year_paid IS NOT NULL
  AND w.prev_year_paid > 0
  AND w.claim_year = w.prev_year + 1
ORDER BY (w.annual_paid - w.prev_year_paid) DESC;

CREATE INDEX IF NOT EXISTS idx_mv_growth_npi ON mv_spending_growth(billing_npi);
CREATE INDEX IF NOT EXISTS idx_mv_growth_year ON mv_spending_growth(claim_year);
CREATE INDEX IF NOT EXISTS idx_mv_growth_pct ON mv_spending_growth(pct_change DESC);
CREATE INDEX IF NOT EXISTS idx_mv_growth_state ON mv_spending_growth(state_code);


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


-- ============================================================
-- 7. Year-over-Year Organization Spending Growth
--    [EN] Compares annual spending by organization (entity_type=2) across consecutive years.
--         Shows raw dollar increase and percentage change. Focused on orgs only for fraud detection.
--    [RU] Сравнивает годовые расходы организаций (entity_type=2) за последовательные годы.
--         Показывает рост в долларах и процентах. Только организации для обнаружения мошенничества.
--    [PT] Compara gastos anuais por organização (entity_type=2) entre anos consecutivos.
--         Mostra aumento em dólares e percentual. Focado em organizações para detecção de fraude.
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_org_yoy_growth AS
WITH yearly AS (
    SELECT
        s.billing_npi,
        EXTRACT(YEAR FROM s.claim_month)::INT AS claim_year,
        SUM(s.total_paid) AS annual_paid,
        SUM(s.total_claims) AS annual_claims,
        SUM(s.total_unique_benes) AS annual_benes,
        COUNT(DISTINCT s.hcpcs_code) AS distinct_hcpcs
    FROM spending s
    JOIN providers p ON p.npi = s.billing_npi AND p.entity_type = 2
    GROUP BY s.billing_npi, EXTRACT(YEAR FROM s.claim_month)
),
with_lag AS (
    SELECT
        billing_npi,
        claim_year,
        annual_paid,
        annual_claims,
        annual_benes,
        distinct_hcpcs,
        LAG(annual_paid) OVER (PARTITION BY billing_npi ORDER BY claim_year) AS prev_year_paid,
        LAG(annual_claims) OVER (PARTITION BY billing_npi ORDER BY claim_year) AS prev_year_claims,
        LAG(claim_year) OVER (PARTITION BY billing_npi ORDER BY claim_year) AS prev_year
    FROM yearly
)
SELECT
    w.billing_npi,
    p.organization_name,
    p.authorized_official_first,
    p.authorized_official_last,
    a.state_code,
    a.city,
    w.claim_year,
    w.prev_year,
    w.annual_paid,
    w.prev_year_paid,
    (w.annual_paid - w.prev_year_paid) AS dollar_increase,
    CASE
        WHEN w.prev_year_paid > 0
        THEN ROUND(((w.annual_paid - w.prev_year_paid) / w.prev_year_paid * 100)::NUMERIC, 1)
        ELSE NULL
    END AS pct_increase,
    w.annual_claims,
    w.prev_year_claims,
    w.annual_benes,
    w.distinct_hcpcs
FROM with_lag w
JOIN providers p ON p.npi = w.billing_npi
LEFT JOIN addresses a ON a.npi = w.billing_npi AND a.address_purpose = 'PRACTICE'
WHERE w.prev_year_paid IS NOT NULL
  AND w.prev_year_paid > 0
  AND w.claim_year = w.prev_year + 1
ORDER BY (w.annual_paid - w.prev_year_paid) DESC;

CREATE INDEX IF NOT EXISTS idx_mv_yoy_npi ON mv_org_yoy_growth(billing_npi);
CREATE INDEX IF NOT EXISTS idx_mv_yoy_year ON mv_org_yoy_growth(claim_year);
CREATE INDEX IF NOT EXISTS idx_mv_yoy_dollar ON mv_org_yoy_growth(dollar_increase DESC);
CREATE INDEX IF NOT EXISTS idx_mv_yoy_pct ON mv_org_yoy_growth(pct_increase DESC);


-- ============================================================
-- 8. Address Clustering — Same Building Fraud Detection
--    [EN] Groups providers by building location (street_number + street_name + zip5).
--         Multiple providers at the same building but different unit numbers is a fraud flag.
--         Uses parsed/normalized address fields for accurate grouping.
--    [RU] Группирует поставщиков по зданию (номер дома + название улицы + индекс).
--         Несколько поставщиков в одном здании, но с разными номерами офисов — признак мошенничества.
--         Использует разобранные/нормализованные адресные поля для точной группировки.
--    [PT] Agrupa provedores por localização do edifício (número + nome da rua + CEP).
--         Múltiplos provedores no mesmo edifício mas com números de unidade diferentes é indicador de fraude.
--         Usa campos de endereço analisados/normalizados para agrupamento preciso.
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_address_clustering AS
SELECT
    COALESCE(a.street_number, '') AS building_number,
    COALESCE(a.street_name, '') AS building_street,
    a.zip5,
    a.city,
    a.state_code,
    COUNT(DISTINCT a.npi) AS provider_count,
    COUNT(DISTINCT a.unit_number) FILTER (WHERE a.unit_number IS NOT NULL) AS distinct_units,
    SUM(ss.total_paid) AS combined_spending,
    SUM(ss.total_claims) AS combined_claims,
    ARRAY_AGG(DISTINCT a.npi ORDER BY a.npi) AS npis,
    ARRAY_AGG(DISTINCT COALESCE(a.unit_number, 'N/A') ORDER BY COALESCE(a.unit_number, 'N/A')) AS unit_numbers,
    ARRAY_AGG(DISTINCT p.organization_name ORDER BY p.organization_name)
        FILTER (WHERE p.organization_name IS NOT NULL) AS org_names
FROM addresses a
JOIN providers p ON p.npi = a.npi
JOIN (
    SELECT billing_npi, SUM(total_paid) AS total_paid, SUM(total_claims) AS total_claims
    FROM spending
    GROUP BY billing_npi
) ss ON ss.billing_npi = a.npi
WHERE a.address_purpose = 'PRACTICE'
  AND a.street_number IS NOT NULL
  AND a.street_name IS NOT NULL
  AND a.zip5 IS NOT NULL
GROUP BY a.street_number, a.street_name, a.zip5, a.city, a.state_code
HAVING COUNT(DISTINCT a.npi) >= 2
ORDER BY combined_spending DESC;

CREATE INDEX IF NOT EXISTS idx_mv_addr_cluster_count ON mv_address_clustering(provider_count DESC);
CREATE INDEX IF NOT EXISTS idx_mv_addr_cluster_zip ON mv_address_clustering(zip5);
CREATE INDEX IF NOT EXISTS idx_mv_addr_cluster_state ON mv_address_clustering(state_code);
CREATE INDEX IF NOT EXISTS idx_mv_addr_cluster_spending ON mv_address_clustering(combined_spending DESC);


-- ============================================================
-- 9. Rapid Ramp Detection — New Organizations with Fast Spending Growth
--    [EN] Identifies organizations that were recently enumerated (NPI activation) and quickly
--         ramped up to high spending levels. A new org going from $0 to millions fast is suspicious.
--    [RU] Выявляет организации, недавно зарегистрированные (активация NPI) и быстро
--         достигшие высоких уровней расходов. Новая организация, быстро достигающая миллионов — подозрительна.
--    [PT] Identifica organizações recentemente registradas (ativação NPI) que rapidamente
--         atingiram altos níveis de gastos. Uma nova org indo de $0 a milhões rapidamente é suspeita.
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_rapid_ramp AS
SELECT
    p.npi AS billing_npi,
    p.organization_name,
    p.authorized_official_first,
    p.authorized_official_last,
    p.enumeration_date,
    a.state_code,
    a.city,
    MIN(s.claim_month) AS first_claim_month,
    MAX(s.claim_month) AS last_claim_month,
    SUM(s.total_paid) AS lifetime_paid,
    SUM(s.total_claims) AS lifetime_claims,
    COUNT(DISTINCT EXTRACT(MONTH FROM s.claim_month) ||
          EXTRACT(YEAR FROM s.claim_month)::TEXT) AS active_months,
    CASE
        WHEN COUNT(DISTINCT EXTRACT(MONTH FROM s.claim_month) ||
             EXTRACT(YEAR FROM s.claim_month)::TEXT) > 0
        THEN ROUND((SUM(s.total_paid) /
             COUNT(DISTINCT EXTRACT(MONTH FROM s.claim_month) ||
             EXTRACT(YEAR FROM s.claim_month)::TEXT))::NUMERIC, 2)
        ELSE 0
    END AS avg_monthly_spend,
    -- Days from NPI enumeration to first claim
    CASE
        WHEN p.enumeration_date IS NOT NULL AND MIN(s.claim_month) IS NOT NULL
        THEN (MIN(s.claim_month) - p.enumeration_date)
        ELSE NULL
    END AS days_to_first_claim
FROM providers p
JOIN spending s ON s.billing_npi = p.npi
LEFT JOIN addresses a ON a.npi = p.npi AND a.address_purpose = 'PRACTICE'
WHERE p.entity_type = 2
  AND p.enumeration_date IS NOT NULL
  AND p.enumeration_date >= '2020-01-01'
GROUP BY p.npi, p.organization_name, p.enumeration_date, a.state_code, a.city
HAVING SUM(s.total_paid) > 100000
ORDER BY SUM(s.total_paid) DESC;

CREATE INDEX IF NOT EXISTS idx_mv_ramp_paid ON mv_rapid_ramp(lifetime_paid DESC);
CREATE INDEX IF NOT EXISTS idx_mv_ramp_enum ON mv_rapid_ramp(enumeration_date);
CREATE INDEX IF NOT EXISTS idx_mv_ramp_state ON mv_rapid_ramp(state_code);


-- ============================================================
-- 10. Composite Fraud Risk Score
--     [EN] Combines multiple fraud signals into a single ranked view per organization.
--          Risk factors: YoY spending spikes, statistical outlier codes, address clustering,
--          rapid ramp-up, and billing network complexity. Higher score = more flags triggered.
--     [RU] Объединяет несколько сигналов мошенничества в единое ранжированное представление по организации.
--          Факторы риска: скачки расходов YoY, статистически аномальные коды, кластеризация адресов,
--          быстрый рост, сложность биллинговой сети. Выше балл = больше триггеров.
--     [PT] Combina múltiplos sinais de fraude em uma visão classificada por organização.
--          Fatores de risco: picos YoY, códigos outlier, clustering de endereço,
--          rampa rápida, complexidade de rede de faturamento. Maior pontuação = mais indicadores.
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_fraud_risk_score AS
WITH org_base AS (
    SELECT
        s.billing_npi,
        p.organization_name,
        p.authorized_official_first,
        p.authorized_official_last,
        a.state_code,
        a.city,
        SUM(s.total_paid) AS lifetime_paid,
        SUM(s.total_claims) AS lifetime_claims,
        MIN(s.claim_month) AS first_claim,
        MAX(s.claim_month) AS last_claim
    FROM spending s
    JOIN providers p ON p.npi = s.billing_npi AND p.entity_type = 2
    LEFT JOIN addresses a ON a.npi = s.billing_npi AND a.address_purpose = 'PRACTICE'
    GROUP BY s.billing_npi, p.organization_name, p.authorized_official_first,
             p.authorized_official_last, a.state_code, a.city
    HAVING SUM(s.total_paid) > 50000
),
-- Flag 1: Large YoY dollar increase (any year)
yoy_flags AS (
    SELECT DISTINCT billing_npi,
        MAX(dollar_increase) AS max_yoy_dollar,
        MAX(pct_increase) AS max_yoy_pct
    FROM mv_org_yoy_growth
    WHERE dollar_increase > 500000 OR pct_increase > 200
    GROUP BY billing_npi
),
-- Flag 2: Statistical outlier on any HCPCS code
outlier_flags AS (
    SELECT billing_npi,
        COUNT(*) AS outlier_code_count,
        MAX(z_score) AS max_z_score
    FROM mv_outlier_providers
    WHERE entity_type = 2
    GROUP BY billing_npi
),
-- Flag 3: Month-over-month spike count
spike_flags AS (
    SELECT billing_npi,
        COUNT(*) AS spike_count,
        MAX(pct_change) AS max_spike_pct
    FROM mv_spending_growth
    WHERE entity_type = 2
    GROUP BY billing_npi
),
-- Flag 4: Shared address (same building, multiple providers)
addr_flags AS (
    SELECT UNNEST(npis) AS billing_npi,
        provider_count AS building_provider_count
    FROM mv_address_clustering
    WHERE provider_count >= 3
),
-- Flag 5: High billing network complexity
network_flags AS (
    SELECT billing_npi,
        COUNT(DISTINCT servicing_npi) AS servicing_partner_count
    FROM mv_billing_servicing_network
    WHERE billing_type = 2
    GROUP BY billing_npi
    HAVING COUNT(DISTINCT servicing_npi) >= 5
)
SELECT
    ob.billing_npi,
    ob.organization_name,
    ob.authorized_official_first,
    ob.authorized_official_last,
    ob.state_code,
    ob.city,
    ob.lifetime_paid,
    ob.lifetime_claims,
    ob.first_claim,
    ob.last_claim,
    -- Individual risk indicators
    CASE WHEN yf.billing_npi IS NOT NULL THEN 1 ELSE 0 END AS flag_yoy_spike,
    yf.max_yoy_dollar,
    yf.max_yoy_pct,
    CASE WHEN olf.billing_npi IS NOT NULL THEN 1 ELSE 0 END AS flag_outlier,
    olf.outlier_code_count,
    olf.max_z_score,
    CASE WHEN sf.billing_npi IS NOT NULL THEN 1 ELSE 0 END AS flag_mom_spike,
    sf.spike_count,
    sf.max_spike_pct,
    CASE WHEN af.billing_npi IS NOT NULL THEN 1 ELSE 0 END AS flag_shared_address,
    af.building_provider_count,
    CASE WHEN nf.billing_npi IS NOT NULL THEN 1 ELSE 0 END AS flag_network_complexity,
    nf.servicing_partner_count,
    -- Composite risk score (0-5): how many flags triggered
    (CASE WHEN yf.billing_npi IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN olf.billing_npi IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN sf.billing_npi IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN af.billing_npi IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN nf.billing_npi IS NOT NULL THEN 1 ELSE 0 END) AS risk_score
FROM org_base ob
LEFT JOIN yoy_flags yf ON yf.billing_npi = ob.billing_npi
LEFT JOIN outlier_flags olf ON olf.billing_npi = ob.billing_npi
LEFT JOIN spike_flags sf ON sf.billing_npi = ob.billing_npi
LEFT JOIN addr_flags af ON af.billing_npi = ob.billing_npi
LEFT JOIN network_flags nf ON nf.billing_npi = ob.billing_npi
WHERE (yf.billing_npi IS NOT NULL
    OR olf.billing_npi IS NOT NULL
    OR sf.billing_npi IS NOT NULL
    OR af.billing_npi IS NOT NULL
    OR nf.billing_npi IS NOT NULL)
ORDER BY
    (CASE WHEN yf.billing_npi IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN olf.billing_npi IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN sf.billing_npi IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN af.billing_npi IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN nf.billing_npi IS NOT NULL THEN 1 ELSE 0 END) DESC,
    ob.lifetime_paid DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_fraud_npi ON mv_fraud_risk_score(billing_npi);
CREATE INDEX IF NOT EXISTS idx_mv_fraud_score ON mv_fraud_risk_score(risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_mv_fraud_state ON mv_fraud_risk_score(state_code);
CREATE INDEX IF NOT EXISTS idx_mv_fraud_paid ON mv_fraud_risk_score(lifetime_paid DESC);


-- ============================================================
-- 11. Average Claim Amount by Provider
--     [EN] Shows the average payment per claim for each provider, along with location.
--          Useful for finding providers with unusually high or low average claim amounts
--          compared to their area. Sortable by highest/lowest, filterable by state.
--     [RU] Показывает среднюю выплату за заявку для каждого поставщика с местоположением.
--          Полезно для поиска поставщиков с необычно высокими или низкими средними суммами заявок
--          по сравнению с их регионом. Сортировка по наибольшим/наименьшим, фильтр по штату.
--     [PT] Mostra o pagamento médio por sinistro para cada provedor, com localização.
--          Útil para encontrar provedores com valores médios de sinistro excepcionalmente
--          altos ou baixos em sua área. Classificável por maior/menor, filtrável por estado.
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_avg_claim_by_provider AS
SELECT
    s.billing_npi,
    p.entity_type,
    p.organization_name,
    p.last_name,
    p.first_name,
    p.authorized_official_first,
    p.authorized_official_last,
    a.state_code,
    a.city,
    a.zip5,
    SUM(s.total_paid) AS lifetime_paid,
    SUM(s.total_claims) AS lifetime_claims,
    SUM(s.total_unique_benes) AS lifetime_benes,
    CASE
        WHEN SUM(s.total_claims) > 0
        THEN ROUND((SUM(s.total_paid) / SUM(s.total_claims))::NUMERIC, 2)
        ELSE 0
    END AS avg_claim_amount,
    COUNT(DISTINCT s.hcpcs_code) AS distinct_hcpcs,
    MIN(s.claim_month) AS first_claim,
    MAX(s.claim_month) AS last_claim
FROM spending s
JOIN providers p ON p.npi = s.billing_npi
LEFT JOIN addresses a ON a.npi = s.billing_npi AND a.address_purpose = 'PRACTICE'
GROUP BY s.billing_npi, p.entity_type, p.organization_name, p.last_name, p.first_name,
         p.authorized_official_first, p.authorized_official_last,
         a.state_code, a.city, a.zip5
HAVING SUM(s.total_claims) >= 10
ORDER BY avg_claim_amount DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_avg_claim_npi ON mv_avg_claim_by_provider(billing_npi);
CREATE INDEX IF NOT EXISTS idx_mv_avg_claim_amount ON mv_avg_claim_by_provider(avg_claim_amount DESC);
CREATE INDEX IF NOT EXISTS idx_mv_avg_claim_state ON mv_avg_claim_by_provider(state_code);
CREATE INDEX IF NOT EXISTS idx_mv_avg_claim_entity ON mv_avg_claim_by_provider(entity_type);


-- ============================================================
-- 12. Authorized Official Network — People Controlling Multiple Organizations
--     [EN] Groups organizations by their authorized official (the person registered as
--          CEO/President/Owner). If one person controls 2+ Medicaid-billing organizations,
--          it's a fraud indicator — especially with shared addresses or rapid ramps.
--          Shows each person's organizations, combined spending, and locations.
--     [RU] Группирует организации по уполномоченному лицу (зарегистрированному как
--          генеральный директор/президент/владелец). Если одно лицо контролирует 2+
--          организации, выставляющие счета Medicaid — это индикатор мошенничества.
--     [PT] Agrupa organizações pelo oficial autorizado (a pessoa registrada como
--          CEO/Presidente/Proprietário). Se uma pessoa controla 2+ organizações que
--          faturam ao Medicaid, é um indicador de fraude.
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_official_network AS
SELECT
    UPPER(TRIM(p.authorized_official_last)) AS official_last,
    UPPER(TRIM(p.authorized_official_first)) AS official_first,
    COUNT(DISTINCT p.npi) AS org_count,
    SUM(ss.total_paid) AS combined_spending,
    SUM(ss.total_claims) AS combined_claims,
    ARRAY_AGG(DISTINCT p.npi ORDER BY p.npi) AS npis,
    ARRAY_AGG(DISTINCT p.organization_name ORDER BY p.organization_name)
        FILTER (WHERE p.organization_name IS NOT NULL) AS org_names,
    ARRAY_AGG(DISTINCT a.state_code ORDER BY a.state_code)
        FILTER (WHERE a.state_code IS NOT NULL) AS states,
    ARRAY_AGG(DISTINCT a.city ORDER BY a.city)
        FILTER (WHERE a.city IS NOT NULL) AS cities,
    COUNT(DISTINCT a.state_code) AS state_count
FROM providers p
JOIN (
    SELECT billing_npi, SUM(total_paid) AS total_paid, SUM(total_claims) AS total_claims
    FROM spending
    GROUP BY billing_npi
) ss ON ss.billing_npi = p.npi
LEFT JOIN addresses a ON a.npi = p.npi AND a.address_purpose = 'PRACTICE'
WHERE p.entity_type = 2
  AND p.authorized_official_last IS NOT NULL
  AND TRIM(p.authorized_official_last) != ''
GROUP BY UPPER(TRIM(p.authorized_official_last)), UPPER(TRIM(p.authorized_official_first))
HAVING COUNT(DISTINCT p.npi) >= 2
ORDER BY COUNT(DISTINCT p.npi) DESC, SUM(ss.total_paid) DESC;

CREATE INDEX IF NOT EXISTS idx_mv_official_count ON mv_official_network(org_count DESC);
CREATE INDEX IF NOT EXISTS idx_mv_official_spending ON mv_official_network(combined_spending DESC);
CREATE INDEX IF NOT EXISTS idx_mv_official_name ON mv_official_network(official_last, official_first);
