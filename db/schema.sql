-- ============================================================
-- Medicaid Provider Spending — Database Schema
-- ============================================================

-- PROVIDERS (from NPPES)
CREATE TABLE providers (
    npi                     CHAR(10) PRIMARY KEY,
    entity_type             SMALLINT NOT NULL,  -- 1=Individual, 2=Organization
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

CREATE INDEX idx_providers_entity_type ON providers(entity_type);
CREATE INDEX idx_providers_org_name ON providers(organization_name) WHERE entity_type = 2;
CREATE INDEX idx_providers_last_name ON providers(last_name) WHERE entity_type = 1;
CREATE INDEX idx_providers_parent_org ON providers(parent_org_name);


-- NORMALIZED ADDRESSES (from NPPES, cleaned + parsed)
CREATE TABLE addresses (
    address_id              SERIAL PRIMARY KEY,
    npi                     CHAR(10) NOT NULL REFERENCES providers(npi),
    address_purpose         TEXT NOT NULL,       -- 'MAILING' or 'PRACTICE'
    street_line_1           TEXT,
    street_line_2           TEXT,
    city                    TEXT,
    state_code              CHAR(2),
    zip5                    CHAR(5),
    zip4                    CHAR(4),
    country_code            CHAR(2) DEFAULT 'US',
    phone                   TEXT,
    fax                     TEXT,
    -- Derived/cleaned fields
    street_number           TEXT,
    street_name             TEXT,
    street_suffix           TEXT,               -- ST, AVE, BLVD, DR
    unit_type               TEXT,               -- STE, APT, UNIT
    unit_number             TEXT,
    UNIQUE(npi, address_purpose)
);

CREATE INDEX idx_addresses_npi ON addresses(npi);
CREATE INDEX idx_addresses_state ON addresses(state_code);
CREATE INDEX idx_addresses_zip5 ON addresses(zip5);
CREATE INDEX idx_addresses_city_state ON addresses(city, state_code);


-- PROVIDER TAXONOMIES / SPECIALTIES (from NPPES)
CREATE TABLE provider_taxonomies (
    id                      SERIAL PRIMARY KEY,
    npi                     CHAR(10) NOT NULL REFERENCES providers(npi),
    taxonomy_code           TEXT NOT NULL,
    license_number          TEXT,
    license_state           CHAR(2),
    is_primary              BOOLEAN DEFAULT FALSE,
    UNIQUE(npi, taxonomy_code)
);

CREATE INDEX idx_taxonomies_npi ON provider_taxonomies(npi);
CREATE INDEX idx_taxonomies_code ON provider_taxonomies(taxonomy_code);


-- HCPCS CODE REFERENCE
CREATE TABLE hcpcs_codes (
    hcpcs_code              TEXT PRIMARY KEY,
    short_description       TEXT,
    long_description        TEXT,
    category                TEXT
);


-- SPENDING FACTS (core fact table from HHS dataset)
CREATE TABLE spending (
    id                      BIGSERIAL PRIMARY KEY,
    billing_npi             CHAR(10) NOT NULL,
    servicing_npi           CHAR(10) NOT NULL,
    hcpcs_code              TEXT NOT NULL,
    claim_month             DATE NOT NULL,      -- First-of-month
    total_unique_benes      INTEGER,
    total_claims            INTEGER,
    total_paid              NUMERIC(15,2)
);

CREATE UNIQUE INDEX idx_spending_natural_key
    ON spending(billing_npi, servicing_npi, hcpcs_code, claim_month);
CREATE INDEX idx_spending_billing ON spending(billing_npi);
CREATE INDEX idx_spending_servicing ON spending(servicing_npi);
CREATE INDEX idx_spending_hcpcs ON spending(hcpcs_code);
CREATE INDEX idx_spending_month ON spending(claim_month);
CREATE INDEX idx_spending_paid ON spending(total_paid DESC);
CREATE INDEX idx_spending_billing_month ON spending(billing_npi, claim_month);
