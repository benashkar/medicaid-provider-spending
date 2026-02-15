# Medicaid Provider Spending — Database & Dashboard Project Plan

## Project Goal

Build a properly indexed relational database from the HHS Medicaid Provider Spending dataset, normalize addresses, enrich with NPPES provider data, and deploy an interactive dashboard on Render.com for visual exploration. All code lives in the `medicaid-provider-spending` GitHub repo.

---

## 1. Repository Structure

### GitHub Repo: `medicaid-provider-spending`

```
medicaid-provider-spending/
├── README.md                          # Project overview + setup instructions
├── .gitignore                         # raw_data/, .env, __pycache__, etc.
├── .env.example                       # Template for env vars (DB URLs, etc.)
├── requirements.txt                   # Python dependencies
├── render.yaml                        # Render Blueprint (IaC for deployment)
├── Dockerfile                         # For Render web service
│
├── db/
│   ├── schema.sql                     # Full DDL: tables, indexes, constraints
│   ├── materialized_views.sql         # Materialized views for dashboard
│   ├── seed_hcpcs.sql                 # HCPCS reference data insert
│   └── migrations/                    # Numbered migration files if schema evolves
│       └── 001_initial.sql
│
├── etl/
│   ├── download.py                    # Downloads HHS ZIP + NPPES ZIP
│   ├── load_spending.py               # Streams spending CSV → PostgreSQL
│   ├── load_nppes.py                  # Filters + loads NPPES, normalizes addresses
│   ├── load_hcpcs.py                  # Loads HCPCS code reference
│   ├── normalize_addresses.py         # usaddress parsing + cleaning logic
│   ├── validate.py                    # Post-load validation queries
│   ├── export_for_render.py           # Produces smaller dataset for Render DB
│   └── refresh_views.py              # Refreshes materialized views
│
├── app/                               # Dashboard web app (Flask)
│   ├── __init__.py                    # Flask app factory
│   ├── config.py                      # Config from env vars
│   ├── models.py                      # SQLAlchemy models (read-only)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── dashboard.py               # Main dashboard routes
│   │   ├── providers.py               # Provider detail + search
│   │   ├── spending.py                # Spending API endpoints (JSON)
│   │   └── addresses.py               # Address/geographic views
│   ├── templates/
│   │   ├── base.html                  # Layout with nav + chart.js/plotly CDN
│   │   ├── dashboard.html             # Main dashboard page
│   │   ├── provider_detail.html       # Single provider view
│   │   ├── search.html                # Provider search
│   │   ├── geographic.html            # State/ZIP heatmap
│   │   └── spending_trends.html       # Time series charts
│   └── static/
│       ├── css/
│       │   └── style.css
│       └── js/
│           └── charts.js              # Chart rendering helpers
│
├── scripts/
│   ├── setup_local.sh                 # Local dev setup (create DB, run migrations)
│   ├── setup_render_db.sh             # Seed Render PostgreSQL
│   ├── load_render_db.sh              # Load exported data into Render DB
│   └── run_etl.sh                     # Full ETL pipeline in order
│
└── tests/
    ├── test_address_normalization.py
    ├── test_etl.py
    └── test_routes.py
```

### `.gitignore`

```gitignore
# Data files (too large for git)
raw_data/
*.csv
*.zip

# Environment
.env
venv/
__pycache__/
*.pyc

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
```

---

## 2. Git Branching Strategy

### Branch Layout

```
main                    ← Production: deployed to Render automatically
├── develop             ← Integration branch: PRs merge here first
├── feature/schema      ← Database DDL + migrations
├── feature/etl         ← Download, load, normalize scripts
├── feature/dashboard   ← Flask app + templates + charts
├── feature/render      ← Render config, Dockerfile, deployment
└── fix/*               ← Bug fixes as needed
```

### Workflow

1. **Create the repo** and push an initial commit with README + .gitignore to `main`
2. **Branch `develop`** from `main`
3. Work in `feature/*` branches, each focused on one area
4. PR from `feature/*` → `develop` (code review / self-review)
5. When `develop` is stable, PR from `develop` → `main` (triggers Render deploy)

### Claude Code — Branch-Specific Prompts

Each Claude Code task below specifies which branch to work on. Start every session with:

```bash
cd ~/medicaid-provider-spending
git checkout <branch-name>
```

---

## 3. Data Sources

### 3A. HHS Medicaid Provider Spending (Primary)

- **URL:** https://opendata.hhs.gov/datasets/medicaid-provider-spending/
- **Format:** ~3.4 GB ZIP → CSV (approx 10 GB uncompressed)
- **Coverage:** Jan 2018 – Dec 2024, fee-for-service + managed care + CHIP
- **Granularity:** One row per billing-provider × servicing-provider × HCPCS code × month
- **Privacy note:** Cells with fewer than 12 claims are suppressed

#### Raw CSV Schema (confirmed from BigQuery ingestion)

| Column | Type | Description |
|---|---|---|
| `BILLING_PROVIDER_NPI_NUM` | STRING (10-digit) | NPI of the billing provider |
| `SERVICING_PROVIDER_NPI_NUM` | STRING (10-digit) | NPI of the servicing/rendering provider |
| `HCPCS_CODE` | STRING | Healthcare Common Procedure Coding System code |
| `CLAIM_FROM_MONTH` | STRING (YYYY-MM) | Month the claims originated |
| `TOTAL_UNIQUE_BENEFICIARIES` | INTEGER | Count of distinct beneficiaries served |
| `TOTAL_CLAIMS` | INTEGER | Number of claims filed |
| `TOTAL_PAID` | NUMERIC | Total Medicaid dollars paid |

**Key observation:** This dataset has NO provider name, address, organization type, or specialty data. Those must be joined from the NPI Registry.

### 3B. NPPES NPI Registry (Enrichment — Required)

- **Download:** https://download.cms.gov/nppes/NPI_Files.html (~8 GB zipped)
- **API:** https://npiregistry.cms.hhs.gov/api/ (for targeted lookups, rate-limited)
- **Updated:** Weekly
- Key fields: NPI, Entity Type, Org Name, Individual Name, Mailing Address, Practice Address, Taxonomy Codes, Authorized Official, Deactivation/Reactivation dates, Parent Org

### 3C. Optional Enrichment (Future Phases)

- **HCPCS Code Descriptions:** CMS HCPCS Level II files
- **OIG Exclusion List (LEIE):** https://oig.hhs.gov/exclusions/
- **OpenPayments:** Industry payments to providers
- **Census/ZCTA data:** For geographic analysis

### Fallback: IPAK BigQuery Mirror

If the HHS site blocks downloads, the dataset is available as a public BigQuery table:
```
project-401c8f7e-90fc-4838-9fc.medicaidproviderspending_1771078072347.medicaid_provider_spending_raw
```

---

## 4. Database Schema (PostgreSQL on Render)

### 4A. Render PostgreSQL Setup

- **Plan:** Render PostgreSQL Standard ($20/mo for 10 GB) or higher
- **Note:** Full dataset is ~50-80 GB indexed. Load an **aggregated/sampled subset** to Render and keep the full dataset locally.
- **Connection:** `DATABASE_URL` env var auto-injected by Render into the web service

### 4B. Sizing Strategy

| Environment | Database | Data Scope | Storage |
|---|---|---|---|
| **Local** (dev/analysis) | Local PostgreSQL or DuckDB | Full 2018–2024 dataset | ~80 GB |
| **Render** (dashboard) | Render PostgreSQL Standard | Aggregated summaries + recent 12 months detail | ~2–5 GB |

The ETL pipeline produces both a full load and a Render-optimized export.

### 4C. Core Tables

```sql
-- ============================================================
-- PROVIDERS (from NPPES)
-- ============================================================
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


-- ============================================================
-- NORMALIZED ADDRESSES (from NPPES, cleaned + parsed)
-- ============================================================
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


-- ============================================================
-- PROVIDER TAXONOMIES / SPECIALTIES (from NPPES)
-- ============================================================
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


-- ============================================================
-- HCPCS CODE REFERENCE
-- ============================================================
CREATE TABLE hcpcs_codes (
    hcpcs_code              TEXT PRIMARY KEY,
    short_description       TEXT,
    long_description        TEXT,
    category                TEXT
);


-- ============================================================
-- SPENDING FACTS (core fact table from HHS dataset)
-- ============================================================
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
```

### 4D. Materialized Views (for Dashboard Performance)

```sql
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
```

---

## 5. Address Normalization Strategy

### Phase 1: Basic Cleaning (Python, no external services)

```python
# 1. Uppercase everything
# 2. Remove punctuation (periods, commas, hashes)
# 3. Standardize abbreviations:
#    STREET → ST, AVENUE → AVE, BOULEVARD → BLVD, DRIVE → DR
#    SUITE → STE, APARTMENT → APT, BUILDING → BLDG
#    NORTH → N, SOUTH → S, EAST → E, WEST → W
# 4. Extract ZIP5 and ZIP4 from 9-digit or ZIP+4 format
# 5. Normalize state names to 2-letter codes
# 6. Strip leading/trailing whitespace
```

### Phase 2: Parse Into Components

Use the `usaddress` Python library:

```python
import usaddress

parsed = usaddress.tag("123 N Main St Ste 200")
# → AddressNumber=123, StreetName=Main, StreetNamePostType=St,
#   OccupancyType=Ste, OccupancyIdentifier=200
```

Map output: `AddressNumber` → `street_number`, `StreetName` → `street_name`, `StreetNamePostType` → `street_suffix`, `OccupancyType` → `unit_type`, `OccupancyIdentifier` → `unit_number`

### Phase 3: Deduplication (Future)

Fuzzy match on (street_number, street_name, zip5) to find multiple NPIs at the same physical location.

---

## 6. Render.com Deployment

### 6A. Architecture

```
┌─────────────────────────────────────────────────┐
│                  Render.com                       │
│                                                   │
│  ┌──────────────────┐    ┌─────────────────────┐ │
│  │  Web Service      │    │  PostgreSQL          │ │
│  │  (Flask app)      │───▶│  (Standard plan)     │ │
│  │  Docker container │    │  DATABASE_URL        │ │
│  │  Port 10000       │    │  auto-injected       │ │
│  └──────────────────┘    └─────────────────────┘ │
│         │                                         │
│         │ Auto-deploy on push to main             │
└─────────┼─────────────────────────────────────────┘
          │
    ┌─────┴─────┐
    │  GitHub    │
    │  main      │
    └───────────┘
```

### 6B. `render.yaml` (Blueprint — Infrastructure as Code)

```yaml
databases:
  - name: medicaid-db
    plan: standard
    databaseName: medicaid_spending
    user: medicaid_user
    region: ohio

services:
  - type: web
    name: medicaid-dashboard
    runtime: docker
    plan: starter
    region: ohio
    repo: https://github.com/YOUR_USERNAME/medicaid-provider-spending
    branch: main
    dockerfilePath: ./Dockerfile
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: medicaid-db
          property: connectionString
      - key: FLASK_ENV
        value: production
      - key: SECRET_KEY
        generateValue: true
    healthCheckPath: /health
```

### 6C. `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY db/ ./db/

EXPOSE 10000

CMD ["gunicorn", "app:create_app()", "--bind", "0.0.0.0:10000", "--workers", "2"]
```

### 6D. `requirements.txt`

```
flask==3.1.*
gunicorn==22.*
psycopg2-binary==2.9.*
sqlalchemy==2.0.*
python-dotenv==1.0.*
usaddress==0.5.*
requests==2.32.*
plotly==6.*
```

### 6E. Dashboard Pages

| Route | Page | What It Shows |
|---|---|---|
| `/` | Dashboard Home | Total spending, provider count, claim count, date range KPIs |
| `/trends` | Spending Trends | Monthly time series chart (Plotly) of total paid, claims, providers |
| `/providers` | Provider Rankings | Searchable/sortable table of top providers by spending |
| `/providers/<npi>` | Provider Detail | Single provider: address, specialties, monthly spending chart, top HCPCS |
| `/geographic` | Geographic View | Choropleth map of spending by state; drill into ZIP-level |
| `/hcpcs` | Procedure Codes | Top HCPCS codes by spending with provider counts |
| `/addresses` | Address Analysis | Providers sharing addresses; normalization quality stats |
| `/health` | Health Check | Returns 200 OK (for Render health check) |
| `/api/spending/monthly` | JSON API | Monthly spending data for charts |
| `/api/providers/search` | JSON API | Provider search by name/NPI/state |
| `/api/providers/<npi>/spending` | JSON API | Per-provider spending time series |

### 6F. Frontend Tech Stack (no build step)

- **Plotly.js** (CDN) — interactive line charts, bar charts, choropleth maps
- **DataTables** (CDN) — sortable/searchable provider tables
- **Bootstrap 5** (CDN) — layout and responsive design
- Plain **Jinja2** templates, no React/webpack/npm needed

---

## 7. Claude Code Implementation Tasks

> **Important:** Reference this plan document in every Claude Code prompt. Start each task by checking out the correct branch.

### Task 0: Repo Initialization
**Branch:** `main` → `develop`
```
Prompt: "Initialize a git repo called medicaid-provider-spending. Create:
1. README.md with project description
2. .gitignore (raw_data/, .env, __pycache__, *.csv, *.zip, venv/)
3. .env.example with DATABASE_URL placeholder
4. requirements.txt with the dependencies listed in the project plan
5. Empty directory structure matching the repo layout in the plan
6. Push to GitHub as a new repo
7. Create a 'develop' branch from main"
```

### Task 1: Database Schema
**Branch:** `feature/schema` (from `develop`)
```
Prompt: "Read the project plan at ./PROJECT_PLAN.md. On branch feature/schema:
1. Create db/schema.sql with ALL the CREATE TABLE and CREATE INDEX 
   statements from section 4C
2. Create db/materialized_views.sql with ALL the materialized views 
   from section 4D
3. Create db/migrations/001_initial.sql that combines both
4. Create scripts/setup_local.sh that creates a local DB and runs the migration
5. PR description for merging into develop"
```

### Task 2: ETL Pipeline
**Branch:** `feature/etl` (from `develop`)
```
Prompt: "Read the project plan at ./PROJECT_PLAN.md. On branch feature/etl:
1. Create etl/download.py — downloads HHS ZIP + NPPES ZIP to raw_data/
2. Create etl/normalize_addresses.py — usaddress parsing + cleaning 
   logic per section 5
3. Create etl/load_spending.py — streams CSV, converts dates, bulk 
   COPY into spending table
4. Create etl/load_nppes.py — filters NPPES to relevant NPIs, 
   normalizes addresses, loads providers + addresses + taxonomies
5. Create etl/load_hcpcs.py — loads HCPCS reference data
6. Create etl/validate.py — post-load validation queries
7. Create etl/refresh_views.py — refreshes all materialized views
8. Create etl/export_for_render.py — produces smaller dataset for 
   Render PostgreSQL (all providers/addresses, aggregated spending, 
   recent 12 months detail)
9. Create scripts/run_etl.sh that runs them all in order
10. Create scripts/load_render_db.sh that loads exported data into 
    Render PostgreSQL
11. All scripts read DATABASE_URL from env vars
12. Handle errors gracefully — log failures, don't crash on bad rows"
```

### Task 3: Flask Dashboard App
**Branch:** `feature/dashboard` (from `develop`)
```
Prompt: "Read the project plan at ./PROJECT_PLAN.md. On branch feature/dashboard:
1. Create Flask app factory in app/__init__.py
2. Create app/config.py reading DATABASE_URL from env
3. Create app/models.py with SQLAlchemy models for all tables + mat views
4. Create route files for each dashboard page per section 6E
5. Create Jinja2 templates using Bootstrap 5 + Plotly.js (CDN):
   - Dashboard home: KPI cards (total spending, provider count, claims)
   - Trends: interactive monthly line chart of spending over time
   - Providers: DataTables sortable table, search by name/NPI/state
   - Provider detail: spending time series, top HCPCS, address info
   - Geographic: US choropleth map colored by state spending
   - HCPCS: top codes table with spending bars
   - Addresses: shared-address analysis table
6. /health endpoint returning 200
7. JSON API endpoints for chart data
8. All queries hit materialized views for performance"
```

### Task 4: Render Deployment Config
**Branch:** `feature/render` (from `develop`)
```
Prompt: "Read the project plan at ./PROJECT_PLAN.md. On branch feature/render:
1. Create the Dockerfile per section 6C
2. Create render.yaml per section 6B
3. Create scripts/setup_render_db.sh that connects to Render PostgreSQL 
   and runs schema + materialized views SQL
4. Ensure /health endpoint exists
5. Gunicorn config: port 10000, 2 workers
6. Update README.md with Render deployment instructions:
   - Create Render account + connect GitHub
   - Use Blueprint (render.yaml) to provision DB + web service
   - Seed the database with scripts/load_render_db.sh
   - Verify deploy at the Render URL"
```

### Task 5: Integration & Deploy
**Branch:** `develop` → `main`
```
Prompt: "Merge all feature branches into develop, resolve conflicts:
1. Merge feature/schema into develop
2. Merge feature/etl into develop  
3. Merge feature/dashboard into develop
4. Merge feature/render into develop
5. Run the app locally to verify
6. PR from develop to main (triggers Render deploy)
7. Seed Render PostgreSQL with exported data"
```

### Task 6: Analysis Views (Post-Deploy)
**Branch:** `feature/analysis` (from `develop`)
```
Prompt: "Create SQL views and dashboard pages for:
1. Top 100 organizations by total lifetime spending
2. Providers billing from the same address (address dedup detection)
3. Month-over-month spending growth by provider (flag >100% increases)
4. Providers >2 std dev above peer mean per HCPCS code
5. Geographic concentration by state and ZIP
6. Billing vs servicing provider relationship network"
```

---

## 8. Estimated Scale

| Item | Estimate |
|---|---|
| Spending CSV rows | ~100–200M |
| Unique NPIs (billing + servicing) | ~1–2M |
| NPPES full file rows | ~8M (filtered to relevant NPIs) |
| Addresses to normalize | ~2–4M (mailing + practice per NPI) |
| **Full local DB** (PostgreSQL, indexed) | ~50–80 GB |
| **Render DB** (sampled/aggregated) | ~2–5 GB |
| Initial full load time | 2–4 hours |
| Render DB seed time | ~10–20 minutes |

---

## 9. Technical Requirements

### Local Development
- **Python 3.11+** with: `psycopg2`, `usaddress`, `flask`, `sqlalchemy`, `plotly`, `gunicorn`
- **PostgreSQL 15+** locally (for full dataset)
- **Docker** (for testing Render container locally)
- **Git + GitHub CLI** (`gh`)
- **Disk:** 150 GB free
- **RAM:** 16 GB recommended

### Render.com
- **Web Service:** Starter plan ($7/mo) — Docker, auto-deploy from `main`
- **PostgreSQL:** Standard plan ($20/mo, 10 GB) — sized for aggregated data
- **Custom domain** (optional)

### Accounts Needed
- GitHub (repo hosting)
- Render.com (deployment + managed PostgreSQL)
- Google account (optional — for BigQuery fallback)

---

## 10. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| HHS download link JS-rendered or changes | Archive ZIP with SHA256 hash; use BigQuery mirror as fallback |
| NPPES file is enormous (~8 GB) | Filter to only NPIs present in spending data |
| Address parsing failures | Log to error file; accept ~95% parse rate |
| Data suppression (cells <12 claims) | Document suppressed rows; do not impute |
| Render PostgreSQL too small for full dataset | Load aggregated/sampled subset; keep full data local |
| Render free tier cold starts | Use Starter paid plan ($7/mo) for always-on |
| Managed care data quality varies by state | Note caveat in dashboard UI |
| Political instability of data source | Archive original ZIP on download |

---

## 11. Execution Order

### Phase 1: Foundation
1. Create GitHub repo `medicaid-provider-spending`, push initial structure to `main`
2. Branch `develop` from `main`
3. `feature/schema` — write and test DDL locally
4. Merge schema into `develop`

### Phase 2: Data Pipeline
5. `feature/etl` — build download + load + normalize scripts
6. Run full ETL locally, validate data
7. Create Render export script (`etl/export_for_render.py`)
8. Merge ETL into `develop`

### Phase 3: Dashboard
9. `feature/dashboard` — build Flask app with all pages
10. Test locally against local PostgreSQL
11. Merge dashboard into `develop`

### Phase 4: Deploy
12. `feature/render` — Dockerfile, render.yaml, deployment docs
13. Merge render config into `develop`
14. PR `develop` → `main` (triggers first Render deploy)
15. Seed Render PostgreSQL with `scripts/load_render_db.sh`
16. Verify dashboard is live at Render URL

### Phase 5: Analysis
17. `feature/analysis` — advanced views and fraud detection queries
18. Merge into `develop` → `main` → auto-deploys to Render
