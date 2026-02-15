"""
Export a smaller dataset for Render PostgreSQL deployment.

Produces:
- All providers and addresses (these are relatively small)
- Aggregated spending summaries (materialized view data)
- Recent 12 months of detailed spending data

Output: CSV files in raw_data/render_export/
"""

import csv
import logging
import os
import sys
from pathlib import Path

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

EXPORT_DIR = Path(__file__).resolve().parent.parent / "raw_data" / "render_export"

EXPORTS = [
    (
        "providers.csv",
        """SELECT npi, entity_type, organization_name, last_name, first_name,
                  middle_name, credential, is_sole_proprietor, is_org_subpart,
                  parent_org_name, parent_org_tin, authorized_official_last,
                  authorized_official_first, authorized_official_phone,
                  enumeration_date, last_update_date, deactivation_date,
                  reactivation_date
           FROM providers""",
    ),
    (
        "addresses.csv",
        """SELECT npi, address_purpose, street_line_1, street_line_2,
                  city, state_code, zip5, zip4, country_code, phone, fax,
                  street_number, street_name, street_suffix, unit_type, unit_number
           FROM addresses""",
    ),
    (
        "provider_taxonomies.csv",
        """SELECT npi, taxonomy_code, license_number, license_state, is_primary
           FROM provider_taxonomies""",
    ),
    (
        "hcpcs_codes.csv",
        "SELECT hcpcs_code, short_description, long_description, category FROM hcpcs_codes",
    ),
    (
        "spending_recent.csv",
        """SELECT billing_npi, servicing_npi, hcpcs_code, claim_month,
                  total_unique_benes, total_claims, total_paid
           FROM spending
           WHERE claim_month >= (SELECT MAX(claim_month) - INTERVAL '12 months' FROM spending)""",
    ),
    (
        "mv_provider_spending_summary.csv",
        "SELECT * FROM mv_provider_spending_summary",
    ),
    (
        "mv_monthly_spending.csv",
        "SELECT * FROM mv_monthly_spending",
    ),
    (
        "mv_state_spending.csv",
        "SELECT * FROM mv_state_spending",
    ),
    (
        "mv_hcpcs_spending.csv",
        "SELECT * FROM mv_hcpcs_spending",
    ),
]


def export_query_to_csv(cur, query: str, filepath: Path) -> int:
    """Execute query and write results to CSV."""
    cur.execute(query)
    columns = [desc[0] for desc in cur.description]
    row_count = 0

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        while True:
            rows = cur.fetchmany(10_000)
            if not rows:
                break
            for row in rows:
                writer.writerow(row)
                row_count += 1

    return row_count


def export_for_render(database_url: str | None = None):
    """Export all tables to CSV files for Render DB seeding."""
    database_url = database_url or os.environ["DATABASE_URL"]
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    log.info("=== Exporting data for Render ===")
    log.info("Output directory: %s", EXPORT_DIR)

    for filename, query in EXPORTS:
        filepath = EXPORT_DIR / filename
        try:
            count = export_query_to_csv(cur, query, filepath)
            size_mb = filepath.stat().st_size / 1e6
            log.info("  %s: %d rows (%.1f MB)", filename, count, size_mb)
        except Exception as e:
            log.error("  %s: FAILED — %s", filename, e)
            conn.rollback()

    cur.close()
    conn.close()

    total_size = sum(f.stat().st_size for f in EXPORT_DIR.glob("*.csv")) / 1e6
    log.info("=== Export complete: %.1f MB total ===", total_size)


def main():
    export_for_render()


if __name__ == "__main__":
    main()
