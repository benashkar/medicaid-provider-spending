-- ============================================================
-- Migration 001: Initial Schema
-- Medicaid Provider Spending Database
-- ============================================================

BEGIN;

-- ============================================================
-- TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS providers (
    npi                     CHAR(10) PRIMARY KEY,
    entity_type             SMALLINT NOT NULL,
    organization_name       TEXT,
    last_name               TEXT,
    first_name              TEXT,
    middle_name             TEXT,
    credential              TEXT,
    is_sole_proprietor      BOOLEAN,
    is_org_subpart          BOOLEAN,
    parent_org_name         TEXT,
    parent_org_tin          TEXT,
    authorized_official_last TEXT,
    authorized_official_first TEXT,
    authorized_official_phone TEXT,
    enumeration_date        DATE,
    last_update_date        DATE,
    deactivation_date       DATE,
    reactivation_date       DATE,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS addresses (
    address_id              SERIAL PRIMARY KEY,
    npi                     CHAR(10) NOT NULL REFERENCES providers(npi),
    address_purpose         TEXT NOT NULL,
    street_line_1           TEXT,
    street_line_2           TEXT,
    city                    TEXT,
    state_code              CHAR(2),
    zip5                    CHAR(5),
    zip4                    CHAR(4),
    country_code            CHAR(2) DEFAULT 'US',
    phone                   TEXT,
    fax                     TEXT,
    street_number           TEXT,
    street_name             TEXT,
    street_suffix           TEXT,
    unit_type               TEXT,
    unit_number             TEXT,
    UNIQUE(npi, address_purpose)
);

CREATE TABLE IF NOT EXISTS provider_taxonomies (
    id                      SERIAL PRIMARY KEY,
    npi                     CHAR(10) NOT NULL REFERENCES providers(npi),
    taxonomy_code           TEXT NOT NULL,
    license_number          TEXT,
    license_state           CHAR(2),
    is_primary              BOOLEAN DEFAULT FALSE,
    UNIQUE(npi, taxonomy_code)
);

CREATE TABLE IF NOT EXISTS hcpcs_codes (
    hcpcs_code              TEXT PRIMARY KEY,
    short_description       TEXT,
    long_description        TEXT,
    category                TEXT
);

CREATE TABLE IF NOT EXISTS spending (
    id                      BIGSERIAL PRIMARY KEY,
    billing_npi             CHAR(10) NOT NULL,
    servicing_npi           CHAR(10) NOT NULL,
    hcpcs_code              TEXT NOT NULL,
    claim_month             DATE NOT NULL,
    total_unique_benes      INTEGER,
    total_claims            INTEGER,
    total_paid              NUMERIC(15,2)
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_providers_entity_type ON providers(entity_type);
CREATE INDEX IF NOT EXISTS idx_providers_org_name ON providers(organization_name) WHERE entity_type = 2;
CREATE INDEX IF NOT EXISTS idx_providers_last_name ON providers(last_name) WHERE entity_type = 1;
CREATE INDEX IF NOT EXISTS idx_providers_parent_org ON providers(parent_org_name);

CREATE INDEX IF NOT EXISTS idx_addresses_npi ON addresses(npi);
CREATE INDEX IF NOT EXISTS idx_addresses_state ON addresses(state_code);
CREATE INDEX IF NOT EXISTS idx_addresses_zip5 ON addresses(zip5);
CREATE INDEX IF NOT EXISTS idx_addresses_city_state ON addresses(city, state_code);

CREATE INDEX IF NOT EXISTS idx_taxonomies_npi ON provider_taxonomies(npi);
CREATE INDEX IF NOT EXISTS idx_taxonomies_code ON provider_taxonomies(taxonomy_code);

CREATE UNIQUE INDEX IF NOT EXISTS idx_spending_natural_key
    ON spending(billing_npi, servicing_npi, hcpcs_code, claim_month);
CREATE INDEX IF NOT EXISTS idx_spending_billing ON spending(billing_npi);
CREATE INDEX IF NOT EXISTS idx_spending_servicing ON spending(servicing_npi);
CREATE INDEX IF NOT EXISTS idx_spending_hcpcs ON spending(hcpcs_code);
CREATE INDEX IF NOT EXISTS idx_spending_month ON spending(claim_month);
CREATE INDEX IF NOT EXISTS idx_spending_paid ON spending(total_paid DESC);
CREATE INDEX IF NOT EXISTS idx_spending_billing_month ON spending(billing_npi, claim_month);

-- ============================================================
-- MATERIALIZED VIEWS
-- ============================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_provider_spending_summary AS
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

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_provider_summary ON mv_provider_spending_summary(billing_npi);
CREATE INDEX IF NOT EXISTS idx_mv_provider_state ON mv_provider_spending_summary(state_code);
CREATE INDEX IF NOT EXISTS idx_mv_provider_paid ON mv_provider_spending_summary(lifetime_paid DESC);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_monthly_spending AS
SELECT
    claim_month,
    COUNT(DISTINCT billing_npi) AS active_providers,
    SUM(total_claims) AS total_claims,
    SUM(total_paid) AS total_paid,
    SUM(total_unique_benes) AS total_benes
FROM spending
GROUP BY claim_month
ORDER BY claim_month;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_monthly ON mv_monthly_spending(claim_month);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_state_spending AS
SELECT
    a.state_code,
    SUM(s.total_paid) AS total_paid,
    SUM(s.total_claims) AS total_claims,
    COUNT(DISTINCT s.billing_npi) AS provider_count,
    SUM(s.total_unique_benes) AS total_benes
FROM spending s
JOIN addresses a ON a.npi = s.billing_npi AND a.address_purpose = 'PRACTICE'
GROUP BY a.state_code;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_state ON mv_state_spending(state_code);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hcpcs_spending AS
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

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_hcpcs ON mv_hcpcs_spending(hcpcs_code);

COMMIT;
