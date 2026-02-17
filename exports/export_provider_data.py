"""
Export providers, addresses, provider_taxonomies, taxonomy_codes, and hcpcs_codes
from PostgreSQL to CSV files and generate a MySQL-compatible import SQL file.

Usage:
    DATABASE_URL="postgresql://..." python exports/export_provider_data.py
"""

import csv
import os
import sys

import psycopg2

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    print("ERROR: Set DATABASE_URL environment variable")
    sys.exit(1)

EXPORT_DIR = os.path.dirname(os.path.abspath(__file__))

TABLES = {
    "providers": {
        "query": """SELECT npi, entity_type, organization_name, last_name, first_name,
                     middle_name, credential, is_sole_proprietor, is_org_subpart,
                     parent_org_name, parent_org_tin,
                     authorized_official_last, authorized_official_first,
                     authorized_official_phone,
                     enumeration_date, last_update_date, deactivation_date, reactivation_date
                     FROM providers ORDER BY npi""",
        "columns": ["npi", "entity_type", "organization_name", "last_name", "first_name",
                     "middle_name", "credential", "is_sole_proprietor", "is_org_subpart",
                     "parent_org_name", "parent_org_tin",
                     "authorized_official_last", "authorized_official_first",
                     "authorized_official_phone",
                     "enumeration_date", "last_update_date", "deactivation_date", "reactivation_date"],
    },
    "addresses": {
        "query": """SELECT npi, address_purpose, street_line_1, street_line_2,
                     city, state_code, zip5, zip4, country_code, phone, fax
                     FROM addresses ORDER BY npi, address_purpose""",
        "columns": ["npi", "address_purpose", "street_line_1", "street_line_2",
                     "city", "state_code", "zip5", "zip4", "country_code", "phone", "fax"],
    },
    "provider_taxonomies": {
        "query": """SELECT npi, taxonomy_code, license_number, license_state, is_primary
                     FROM provider_taxonomies ORDER BY npi, taxonomy_code""",
        "columns": ["npi", "taxonomy_code", "license_number", "license_state", "is_primary"],
    },
    "taxonomy_codes": {
        "query": """SELECT taxonomy_code, grouping, classification, specialization,
                     display_name, definition, section
                     FROM taxonomy_codes ORDER BY taxonomy_code""",
        "columns": ["taxonomy_code", "grouping", "classification", "specialization",
                     "display_name", "definition", "section"],
    },
    "hcpcs_codes": {
        "query": """SELECT hcpcs_code, short_description, long_description, category
                     FROM hcpcs_codes ORDER BY hcpcs_code""",
        "columns": ["hcpcs_code", "short_description", "long_description", "category"],
    },
}


def export_csv(conn, table_name, table_def):
    """Export a table to CSV using server-side cursor for memory efficiency."""
    path = os.path.join(EXPORT_DIR, f"{table_name}.csv")
    print(f"Exporting {table_name} to {path}...", flush=True)

    cur = conn.cursor(name=f"export_{table_name}")
    cur.itersize = 50000
    cur.execute(table_def["query"])

    count = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(table_def["columns"])
        for row in cur:
            writer.writerow([
                str(v).strip() if isinstance(v, str) else
                ("1" if v is True else "0" if v is False else
                 str(v) if v is not None else "")
                for v in row
            ])
            count += 1
            if count % 1000000 == 0:
                print(f"  {count:,} rows...", flush=True)

    cur.close()
    print(f"  Done: {count:,} rows", flush=True)
    return count


def main():
    conn = psycopg2.connect(DB_URL)
    # autocommit must be False for server-side (named) cursors
    conn.autocommit = False

    counts = {}
    for table_name, table_def in TABLES.items():
        counts[table_name] = export_csv(conn, table_name, table_def)

    conn.close()

    print("\n=== Export Summary ===")
    for t, c in counts.items():
        print(f"  {t}: {c:,} rows")
    print("Done!")


if __name__ == "__main__":
    main()
