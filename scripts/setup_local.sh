#!/usr/bin/env bash
# Setup local PostgreSQL database for Medicaid Provider Spending
set -euo pipefail

DB_NAME="${DB_NAME:-medicaid_spending}"
DB_USER="${DB_USER:-postgres}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Medicaid Provider Spending — Local DB Setup ==="

# Create database if it doesn't exist
echo "Creating database '$DB_NAME' (if not exists)..."
psql -U "$DB_USER" -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" \
    | grep -q 1 \
    || psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME"

echo "Running migration 001_initial.sql..."
psql -U "$DB_USER" -d "$DB_NAME" -f "$PROJECT_DIR/db/migrations/001_initial.sql"

echo "=== Local DB setup complete ==="
echo "Connection: postgresql://$DB_USER@localhost:5432/$DB_NAME"
