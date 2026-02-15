#!/usr/bin/env bash
# Run the full ETL pipeline for Medicaid Provider Spending
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Medicaid Provider Spending — Full ETL Pipeline ==="
echo "Project directory: $PROJECT_DIR"

# Check DATABASE_URL
if [ -z "${DATABASE_URL:-}" ]; then
    if [ -f "$PROJECT_DIR/.env" ]; then
        export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
    fi
fi

if [ -z "${DATABASE_URL:-}" ]; then
    echo "ERROR: DATABASE_URL not set. Create .env or export it."
    exit 1
fi

echo "Database: ${DATABASE_URL%%@*}@..."

# Step 1: Download data
echo ""
echo "=== Step 1: Download data ==="
python -m etl.download

# Step 2: Run schema migration
echo ""
echo "=== Step 2: Apply database schema ==="
psql "$DATABASE_URL" -f "$PROJECT_DIR/db/migrations/001_initial.sql"

# Step 3: Load spending data
echo ""
echo "=== Step 3: Load spending data ==="
python -m etl.load_spending

# Step 4: Load NPPES data (filtered to spending NPIs)
echo ""
echo "=== Step 4: Load NPPES provider data ==="
python -m etl.load_nppes

# Step 5: Load HCPCS codes
echo ""
echo "=== Step 5: Load HCPCS codes ==="
python -m etl.load_hcpcs

# Step 6: Refresh materialized views
echo ""
echo "=== Step 6: Refresh materialized views ==="
python -m etl.refresh_views

# Step 7: Validate
echo ""
echo "=== Step 7: Validate data ==="
python -m etl.validate

# Step 8: Export for Render
echo ""
echo "=== Step 8: Export for Render ==="
python -m etl.export_for_render

echo ""
echo "=== ETL pipeline complete ==="
