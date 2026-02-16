"""
Load NUCC Health Care Provider Taxonomy Code Set into PostgreSQL.

Usage:
    python -m etl.load_taxonomy

Downloads or reads the NUCC taxonomy CSV and loads taxonomy codes with their
descriptions, groupings, classifications, and specializations into the
taxonomy_codes reference table. Uses UPSERT (ON CONFLICT DO UPDATE) to
safely re-run without duplicating data.

Source: https://www.nucc.org/index.php/code-sets-mainmenu-41/provider-taxonomy-mainmenu-40/csv-mainmenu-57
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

RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "raw_data"

# NUCC taxonomy CSV URL (Version 25.1 — current through 1/1/2026)
NUCC_CSV_URL = "https://www.nucc.org/images/stories/CSV/nucc_taxonomy_251.csv"


def find_taxonomy_file() -> Path | None:
    """Find a local NUCC taxonomy CSV file in raw_data/."""
    for pattern in ["nucc_taxonomy*.csv", "NUCC_taxonomy*.csv", "nucc_taxonomy*.CSV"]:
        candidates = list(RAW_DATA_DIR.glob(pattern))
        if candidates:
            return max(candidates, key=lambda p: p.stat().st_mtime)
    return None


def download_taxonomy_file() -> Path:
    """Download the NUCC taxonomy CSV from nucc.org."""
    import urllib.request
    dest = RAW_DATA_DIR / "nucc_taxonomy.csv"
    log.info("Downloading NUCC taxonomy CSV from %s", NUCC_CSV_URL)
    urllib.request.urlretrieve(NUCC_CSV_URL, dest)
    log.info("Downloaded to %s", dest)
    return dest


def load_taxonomy(database_url: str | None = None):
    """Load NUCC taxonomy codes into the taxonomy_codes table."""
    database_url = database_url or os.environ["DATABASE_URL"]

    # Find or download the CSV
    csv_path = find_taxonomy_file()
    if not csv_path:
        csv_path = download_taxonomy_file()

    log.info("Loading taxonomy codes from %s", csv_path)

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    # Create table if not exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS taxonomy_codes (
            taxonomy_code   TEXT PRIMARY KEY,
            grouping        TEXT,
            classification  TEXT,
            specialization  TEXT,
            display_name    TEXT,
            definition      TEXT,
            section         TEXT
        )
    """)
    conn.commit()

    loaded = 0
    skipped = 0

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row.get("Code", "").strip()
            if not code:
                skipped += 1
                continue

            grouping = row.get("Grouping", "").strip() or None
            classification = row.get("Classification", "").strip() or None
            specialization = row.get("Specialization", "").strip() or None
            display_name = row.get("Display Name", "").strip() or None
            definition = row.get("Definition", "").strip() or None
            section = row.get("Section", "").strip() or None

            try:
                cur.execute("""
                    INSERT INTO taxonomy_codes
                        (taxonomy_code, grouping, classification, specialization,
                         display_name, definition, section)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (taxonomy_code) DO UPDATE SET
                        grouping = EXCLUDED.grouping,
                        classification = EXCLUDED.classification,
                        specialization = EXCLUDED.specialization,
                        display_name = EXCLUDED.display_name,
                        definition = EXCLUDED.definition,
                        section = EXCLUDED.section
                """, (code, grouping, classification, specialization,
                      display_name, definition, section))
                loaded += 1
            except Exception as e:
                log.debug("Insert error for %s: %s", code, e)
                conn.rollback()
                skipped += 1

    conn.commit()
    cur.close()
    conn.close()

    log.info("Taxonomy load complete: %d codes loaded, %d skipped", loaded, skipped)


def main():
    load_taxonomy()


if __name__ == "__main__":
    main()
