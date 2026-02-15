#!/usr/bin/env bash
# Initialize Render PostgreSQL with schema and materialized views
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Setting up Render PostgreSQL ==="

if [ -z "${RENDER_DATABASE_URL:-}" ]; then
    if [ -z "${DATABASE_URL:-}" ]; then
        echo "ERROR: Set RENDER_DATABASE_URL or DATABASE_URL"
        exit 1
    fi
    RENDER_DATABASE_URL="$DATABASE_URL"
fi

echo "Target: ${RENDER_DATABASE_URL%%@*}@..."

echo "Running migration..."
psql "$RENDER_DATABASE_URL" -f "$PROJECT_DIR/db/migrations/001_initial.sql"

echo "=== Render DB schema applied ==="
