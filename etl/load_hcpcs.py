"""Load HCPCS code reference data into PostgreSQL."""

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

RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "raw_data"


def find_hcpcs_file() -> Path | None:
    """Find HCPCS reference file in raw_data."""
    candidates = list(RAW_DATA_DIR.glob("*hcpcs*")) + list(RAW_DATA_DIR.glob("*HCPCS*"))
    for c in candidates:
        if c.suffix.lower() in (".csv", ".tsv", ".txt"):
            return c
    return None


def load_hcpcs_from_spending(database_url: str):
    """
    Extract distinct HCPCS codes from spending table as a fallback
    when no HCPCS reference file is available.
    """
    log.info("No HCPCS file found — extracting codes from spending table")
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO hcpcs_codes (hcpcs_code)
        SELECT DISTINCT hcpcs_code FROM spending
        WHERE hcpcs_code IS NOT NULL
        ON CONFLICT (hcpcs_code) DO NOTHING
    """)
    inserted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    log.info("Inserted %d HCPCS codes from spending data", inserted)


def load_hcpcs_from_file(file_path: Path, database_url: str):
    """Load HCPCS codes from a reference CSV file."""
    log.info("Loading HCPCS codes from %s", file_path)
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    loaded = 0
    skipped = 0

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = None
            short_desc = None
            long_desc = None
            category = None

            # Try common column name patterns
            for key in row:
                kl = key.lower().strip()
                if "hcpcs" in kl and "code" in kl:
                    code = row[key].strip()
                elif kl in ("code", "hcpc"):
                    code = row[key].strip()
                elif "short" in kl and "desc" in kl:
                    short_desc = row[key].strip()
                elif "long" in kl and "desc" in kl:
                    long_desc = row[key].strip()
                elif "desc" in kl and not short_desc:
                    short_desc = row[key].strip()
                elif "categ" in kl:
                    category = row[key].strip()

            if not code:
                skipped += 1
                continue

            try:
                cur.execute(
                    """INSERT INTO hcpcs_codes (hcpcs_code, short_description, long_description, category)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (hcpcs_code) DO UPDATE SET
                        short_description = COALESCE(EXCLUDED.short_description, hcpcs_codes.short_description),
                        long_description = COALESCE(EXCLUDED.long_description, hcpcs_codes.long_description),
                        category = COALESCE(EXCLUDED.category, hcpcs_codes.category)""",
                    (code, short_desc or None, long_desc or None, category or None),
                )
                loaded += 1
            except Exception as e:
                log.debug("HCPCS insert error for %s: %s", code, e)
                conn.rollback()
                skipped += 1
                continue

    conn.commit()
    cur.close()
    conn.close()
    log.info("HCPCS load complete: %d loaded, %d skipped", loaded, skipped)


def load_hcpcs(database_url: str | None = None):
    """Load HCPCS codes from file or spending table."""
    database_url = database_url or os.environ["DATABASE_URL"]

    hcpcs_file = find_hcpcs_file()
    if hcpcs_file:
        load_hcpcs_from_file(hcpcs_file, database_url)
    else:
        load_hcpcs_from_spending(database_url)


def main():
    load_hcpcs()


if __name__ == "__main__":
    main()
