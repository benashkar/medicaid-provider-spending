"""Load HHS Medicaid Provider Spending CSV into PostgreSQL."""

import csv
import io
import logging
import os
import sys
from datetime import date
from pathlib import Path

import psycopg2
from psycopg2 import sql

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "raw_data"
CSV_FILE = RAW_DATA_DIR / "medicaid_provider_spending.csv"

# Column mapping: CSV header → DB column
COLUMN_MAP = {
    "BILLING_PROVIDER_NPI_NUM": "billing_npi",
    "SERVICING_PROVIDER_NPI_NUM": "servicing_npi",
    "HCPCS_CODE": "hcpcs_code",
    "CLAIM_FROM_MONTH": "claim_month",
    "TOTAL_UNIQUE_BENEFICIARIES": "total_unique_benes",
    "TOTAL_CLAIMS": "total_claims",
    "TOTAL_PAID": "total_paid",
}

DB_COLUMNS = [
    "billing_npi", "servicing_npi", "hcpcs_code", "claim_month",
    "total_unique_benes", "total_claims", "total_paid",
]

BATCH_SIZE = 50_000


def parse_claim_month(val: str) -> date | None:
    """Parse YYYY-MM into first-of-month date."""
    if not val:
        return None
    try:
        parts = val.strip().split("-")
        return date(int(parts[0]), int(parts[1]), 1)
    except (ValueError, IndexError):
        return None


def parse_int(val: str) -> int | None:
    """Parse integer, returning None for empty/invalid."""
    if not val or val.strip() == "":
        return None
    try:
        return int(val.strip())
    except ValueError:
        return None


def parse_decimal(val: str) -> float | None:
    """Parse decimal/currency value."""
    if not val or val.strip() == "":
        return None
    try:
        return float(val.strip().replace(",", ""))
    except ValueError:
        return None


def transform_row(row: dict) -> tuple | None:
    """Transform a CSV row dict into a tuple for DB insertion."""
    billing_npi = row.get("BILLING_PROVIDER_NPI_NUM", "").strip()
    servicing_npi = row.get("SERVICING_PROVIDER_NPI_NUM", "").strip()
    hcpcs_code = row.get("HCPCS_CODE", "").strip()
    claim_month = parse_claim_month(row.get("CLAIM_FROM_MONTH", ""))

    if not billing_npi or not servicing_npi or not hcpcs_code or not claim_month:
        return None

    return (
        billing_npi[:10],
        servicing_npi[:10],
        hcpcs_code,
        claim_month,
        parse_int(row.get("TOTAL_UNIQUE_BENEFICIARIES", "")),
        parse_int(row.get("TOTAL_CLAIMS", "")),
        parse_decimal(row.get("TOTAL_PAID", "")),
    )


def copy_batch(cur, batch: list[tuple]):
    """Use COPY for fast bulk insertion."""
    buf = io.StringIO()
    for row in batch:
        line = "\t".join(
            "\\N" if v is None else str(v) for v in row
        )
        buf.write(line + "\n")
    buf.seek(0)
    cur.copy_from(
        buf,
        "spending",
        columns=DB_COLUMNS,
        null="\\N",
    )


def load_spending(csv_path: Path | None = None, database_url: str | None = None):
    """Stream spending CSV into PostgreSQL using COPY."""
    csv_path = csv_path or CSV_FILE
    database_url = database_url or os.environ["DATABASE_URL"]

    if not csv_path.exists():
        log.error("CSV file not found: %s", csv_path)
        sys.exit(1)

    log.info("Loading spending data from %s", csv_path)
    conn = psycopg2.connect(database_url)
    conn.autocommit = False
    cur = conn.cursor()

    # Truncate for clean reload
    cur.execute("TRUNCATE TABLE spending RESTART IDENTITY CASCADE")
    log.info("Truncated spending table")

    total_rows = 0
    skipped = 0
    batch = []

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            transformed = transform_row(row)
            if transformed is None:
                skipped += 1
                continue

            batch.append(transformed)
            if len(batch) >= BATCH_SIZE:
                try:
                    copy_batch(cur, batch)
                    conn.commit()
                    total_rows += len(batch)
                    log.info("Loaded %d rows (%d skipped)", total_rows, skipped)
                except Exception as e:
                    conn.rollback()
                    log.error("Batch insert failed at row %d: %s", total_rows, e)
                    # Try inserting one-by-one for this batch
                    for single in batch:
                        try:
                            cur.execute(
                                """INSERT INTO spending
                                   (billing_npi, servicing_npi, hcpcs_code, claim_month,
                                    total_unique_benes, total_claims, total_paid)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                                   ON CONFLICT ON CONSTRAINT idx_spending_natural_key
                                   DO NOTHING""",
                                single,
                            )
                            conn.commit()
                            total_rows += 1
                        except Exception as e2:
                            conn.rollback()
                            skipped += 1
                batch = []

    # Final batch
    if batch:
        try:
            copy_batch(cur, batch)
            conn.commit()
            total_rows += len(batch)
        except Exception as e:
            conn.rollback()
            log.error("Final batch failed: %s", e)
            skipped += len(batch)

    cur.close()
    conn.close()

    log.info("=== Spending load complete ===")
    log.info("Total rows loaded: %d", total_rows)
    log.info("Rows skipped: %d", skipped)


def main():
    load_spending()


if __name__ == "__main__":
    main()
