# Medicaid Provider Spending — Database & Dashboard

A relational database and interactive dashboard built from the [HHS Medicaid Provider Spending dataset](https://opendata.hhs.gov/datasets/medicaid-provider-spending/), enriched with provider data from the NPPES NPI Registry.

## Features

- Normalized PostgreSQL database with indexed spending facts, provider details, and parsed addresses
- ETL pipeline for downloading, loading, and normalizing HHS + NPPES data
- Interactive Flask dashboard with Plotly.js charts, DataTables, and Bootstrap 5
- Geographic spending analysis by state and ZIP code
- Provider search and detail views with spending trends
- HCPCS procedure code analysis
- Deployed on Render.com with auto-deploy from `main`

## Data Sources

- **HHS Medicaid Provider Spending** — ~200M rows, Jan 2018 – Dec 2024
- **NPPES NPI Registry** — Provider names, addresses, specialties

## Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Git

### Setup

```bash
git clone https://github.com/benashkar/medicaid-provider-spending.git
cd medicaid-provider-spending
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your local database URL
```

### Run ETL Pipeline

```bash
bash scripts/run_etl.sh
```

### Run Dashboard Locally

```bash
flask --app app run --debug
```

## Render Deployment

1. Create a [Render](https://render.com) account and connect your GitHub repo
2. Use the Blueprint (`render.yaml`) to provision the database and web service
3. Seed the Render database: `bash scripts/load_render_db.sh`
4. The dashboard auto-deploys on push to `main`

## Project Structure

```
medicaid-provider-spending/
├── db/           # SQL schema, migrations, materialized views
├── etl/          # Data download, load, and normalization scripts
├── app/          # Flask dashboard application
├── scripts/      # Shell scripts for setup and ETL
└── tests/        # Test suite
```

## License

MIT
