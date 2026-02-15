#!/usr/bin/env bash
# Load exported data into Render PostgreSQL
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
EXPORT_DIR="$PROJECT_DIR/raw_data/render_export"

echo "=== Loading data into Render PostgreSQL ==="

# Check for Render DATABASE_URL
if [ -z "${RENDER_DATABASE_URL:-}" ]; then
    if [ -z "${DATABASE_URL:-}" ]; then
        echo "ERROR: Set RENDER_DATABASE_URL or DATABASE_URL"
        exit 1
    fi
    RENDER_DATABASE_URL="$DATABASE_URL"
fi

echo "Target: ${RENDER_DATABASE_URL%%@*}@..."

# Check export files exist
if [ ! -d "$EXPORT_DIR" ]; then
    echo "ERROR: Export directory not found: $EXPORT_DIR"
    echo "Run the ETL pipeline first: bash scripts/run_etl.sh"
    exit 1
fi

# Apply schema
echo ""
echo "=== Applying schema ==="
psql "$RENDER_DATABASE_URL" -f "$PROJECT_DIR/db/migrations/001_initial.sql"

# Load providers
echo ""
echo "=== Loading providers ==="
psql "$RENDER_DATABASE_URL" -c "TRUNCATE providers CASCADE"
psql "$RENDER_DATABASE_URL" -c "\COPY providers(npi, entity_type, organization_name, last_name, first_name, middle_name, credential, is_sole_proprietor, is_org_subpart, parent_org_name, parent_org_tin, authorized_official_last, authorized_official_first, authorized_official_phone, enumeration_date, last_update_date, deactivation_date, reactivation_date) FROM '$EXPORT_DIR/providers.csv' CSV HEADER"

# Load addresses
echo ""
echo "=== Loading addresses ==="
psql "$RENDER_DATABASE_URL" -c "\COPY addresses(npi, address_purpose, street_line_1, street_line_2, city, state_code, zip5, zip4, country_code, phone, fax, street_number, street_name, street_suffix, unit_type, unit_number) FROM '$EXPORT_DIR/addresses.csv' CSV HEADER"

# Load taxonomies
echo ""
echo "=== Loading taxonomies ==="
psql "$RENDER_DATABASE_URL" -c "\COPY provider_taxonomies(npi, taxonomy_code, license_number, license_state, is_primary) FROM '$EXPORT_DIR/provider_taxonomies.csv' CSV HEADER"

# Load HCPCS codes
echo ""
echo "=== Loading HCPCS codes ==="
psql "$RENDER_DATABASE_URL" -c "\COPY hcpcs_codes(hcpcs_code, short_description, long_description, category) FROM '$EXPORT_DIR/hcpcs_codes.csv' CSV HEADER"

# Load recent spending
echo ""
echo "=== Loading recent spending data ==="
psql "$RENDER_DATABASE_URL" -c "TRUNCATE spending RESTART IDENTITY"
psql "$RENDER_DATABASE_URL" -c "\COPY spending(billing_npi, servicing_npi, hcpcs_code, claim_month, total_unique_benes, total_claims, total_paid) FROM '$EXPORT_DIR/spending_recent.csv' CSV HEADER"

# Refresh materialized views
echo ""
echo "=== Refreshing materialized views ==="
psql "$RENDER_DATABASE_URL" -f "$PROJECT_DIR/db/materialized_views.sql" 2>/dev/null || true
psql "$RENDER_DATABASE_URL" -c "REFRESH MATERIALIZED VIEW mv_provider_spending_summary"
psql "$RENDER_DATABASE_URL" -c "REFRESH MATERIALIZED VIEW mv_monthly_spending"
psql "$RENDER_DATABASE_URL" -c "REFRESH MATERIALIZED VIEW mv_state_spending"
psql "$RENDER_DATABASE_URL" -c "REFRESH MATERIALIZED VIEW mv_hcpcs_spending"

# Verify
echo ""
echo "=== Verification ==="
psql "$RENDER_DATABASE_URL" -c "SELECT 'providers' AS tbl, COUNT(*) FROM providers UNION ALL SELECT 'addresses', COUNT(*) FROM addresses UNION ALL SELECT 'taxonomies', COUNT(*) FROM provider_taxonomies UNION ALL SELECT 'hcpcs_codes', COUNT(*) FROM hcpcs_codes UNION ALL SELECT 'spending', COUNT(*) FROM spending ORDER BY tbl"

echo ""
echo "=== Render DB load complete ==="
