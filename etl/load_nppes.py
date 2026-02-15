"""Load NPPES NPI Registry data into PostgreSQL (providers, addresses, taxonomies)."""

import csv
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

import psycopg2

from etl.normalize_addresses import normalize_address

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "raw_data"
NPPES_DIR = RAW_DATA_DIR / "nppes"

BATCH_SIZE = 10_000


def find_nppes_csv() -> Path | None:
    """Find the main NPPES data file."""
    candidates = list(NPPES_DIR.glob("npidata_pfile_*.csv"))
    if candidates:
        return sorted(candidates, key=lambda p: p.stat().st_size, reverse=True)[0]
    return None


def parse_date(val: str) -> date | None:
    """Parse MM/DD/YYYY date from NPPES."""
    if not val or val.strip() == "":
        return None
    try:
        return datetime.strptime(val.strip(), "%m/%d/%Y").date()
    except ValueError:
        return None


def parse_bool(val: str) -> bool | None:
    """Parse Y/N boolean."""
    if not val:
        return None
    val = val.strip().upper()
    if val == "Y":
        return True
    if val == "N":
        return False
    return None


def get_relevant_npis(database_url: str) -> set[str]:
    """Get the set of NPIs from the spending table to filter NPPES."""
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT npi FROM (
            SELECT billing_npi AS npi FROM spending
            UNION
            SELECT servicing_npi AS npi FROM spending
        ) all_npis
    """)
    npis = {row[0].strip() for row in cur.fetchall()}
    cur.close()
    conn.close()
    log.info("Found %d unique NPIs in spending data", len(npis))
    return npis


def load_nppes(database_url: str | None = None, filter_to_spending: bool = True):
    """Load NPPES data, optionally filtered to NPIs in spending table."""
    database_url = database_url or os.environ["DATABASE_URL"]

    nppes_csv = find_nppes_csv()
    if not nppes_csv:
        log.error("NPPES CSV not found in %s", NPPES_DIR)
        sys.exit(1)

    log.info("Loading NPPES from %s", nppes_csv)

    relevant_npis = None
    if filter_to_spending:
        relevant_npis = get_relevant_npis(database_url)
        if not relevant_npis:
            log.warning("No NPIs found in spending table — loading all NPPES records")
            relevant_npis = None

    conn = psycopg2.connect(database_url)
    conn.autocommit = False
    cur = conn.cursor()

    # Clear existing data
    cur.execute("TRUNCATE TABLE provider_taxonomies CASCADE")
    cur.execute("TRUNCATE TABLE addresses CASCADE")
    cur.execute("TRUNCATE TABLE providers CASCADE")
    conn.commit()
    log.info("Truncated providers, addresses, taxonomies tables")

    providers_loaded = 0
    addresses_loaded = 0
    taxonomies_loaded = 0
    skipped = 0

    with open(nppes_csv, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        provider_batch = []
        address_batch = []
        taxonomy_batch = []

        for row in reader:
            npi = row.get("NPI", "").strip()
            if not npi or len(npi) != 10:
                skipped += 1
                continue

            if relevant_npis and npi not in relevant_npis:
                continue

            entity_type = row.get("Entity Type Code", "").strip()
            if entity_type not in ("1", "2"):
                skipped += 1
                continue

            # Provider record
            provider = (
                npi,
                int(entity_type),
                row.get("Provider Organization Name (Legal Business Name)", "").strip() or None,
                row.get("Provider Last Name (Legal Name)", "").strip() or None,
                row.get("Provider First Name", "").strip() or None,
                row.get("Provider Middle Name", "").strip() or None,
                row.get("Provider Credential Text", "").strip() or None,
                parse_bool(row.get("Is Sole Proprietor")),
                parse_bool(row.get("Is Organization Subpart")),
                row.get("Parent Organization LBN", "").strip() or None,
                row.get("Parent Organization TIN", "").strip() or None,
                row.get("Authorized Official Last Name", "").strip() or None,
                row.get("Authorized Official First Name", "").strip() or None,
                row.get("Authorized Official Telephone Number", "").strip() or None,
                parse_date(row.get("Provider Enumeration Date")),
                parse_date(row.get("Last Update Date")),
                parse_date(row.get("NPI Deactivation Date")),
                parse_date(row.get("NPI Reactivation Date")),
            )
            provider_batch.append(provider)

            # Mailing address
            mailing_addr = normalize_address(
                street_line_1=row.get("Provider First Line Business Mailing Address"),
                street_line_2=row.get("Provider Second Line Business Mailing Address"),
                city=row.get("Provider Business Mailing Address City Name"),
                state=row.get("Provider Business Mailing Address State Name"),
                zip_code=row.get("Provider Business Mailing Address Postal Code"),
                phone=row.get("Provider Business Mailing Address Telephone Number"),
                fax=row.get("Provider Business Mailing Address Fax Number"),
            )
            address_batch.append((npi, "MAILING", mailing_addr))

            # Practice address
            practice_addr = normalize_address(
                street_line_1=row.get("Provider First Line Business Practice Location Address"),
                street_line_2=row.get("Provider Second Line Business Practice Location Address"),
                city=row.get("Provider Business Practice Location Address City Name"),
                state=row.get("Provider Business Practice Location Address State Name"),
                zip_code=row.get("Provider Business Practice Location Address Postal Code"),
                phone=row.get("Provider Business Practice Location Address Telephone Number"),
                fax=row.get("Provider Business Practice Location Address Fax Number"),
            )
            address_batch.append((npi, "PRACTICE", practice_addr))

            # Taxonomies (up to 15 per NPI)
            for i in range(1, 16):
                tax_code = row.get(f"Healthcare Provider Taxonomy Code_{i}", "").strip()
                if not tax_code:
                    continue
                license_num = row.get(f"Provider License Number_{i}", "").strip() or None
                license_state = row.get(f"Provider License Number State Code_{i}", "").strip() or None
                is_primary = row.get(f"Healthcare Provider Primary Taxonomy Switch_{i}", "").strip().upper() == "Y"
                taxonomy_batch.append((npi, tax_code, license_num, license_state, is_primary))

            # Flush batches
            if len(provider_batch) >= BATCH_SIZE:
                _flush_providers(cur, provider_batch)
                _flush_addresses(cur, address_batch)
                _flush_taxonomies(cur, taxonomy_batch)
                conn.commit()
                providers_loaded += len(provider_batch)
                addresses_loaded += len(address_batch)
                taxonomies_loaded += len(taxonomy_batch)
                log.info(
                    "Loaded %d providers, %d addresses, %d taxonomies (%d skipped)",
                    providers_loaded, addresses_loaded, taxonomies_loaded, skipped,
                )
                provider_batch = []
                address_batch = []
                taxonomy_batch = []

        # Final batch
        if provider_batch:
            _flush_providers(cur, provider_batch)
            _flush_addresses(cur, address_batch)
            _flush_taxonomies(cur, taxonomy_batch)
            conn.commit()
            providers_loaded += len(provider_batch)
            addresses_loaded += len(address_batch)
            taxonomies_loaded += len(taxonomy_batch)

    cur.close()
    conn.close()

    log.info("=== NPPES load complete ===")
    log.info("Providers: %d", providers_loaded)
    log.info("Addresses: %d", addresses_loaded)
    log.info("Taxonomies: %d", taxonomies_loaded)
    log.info("Skipped: %d", skipped)


def _flush_providers(cur, batch):
    """Insert provider batch."""
    for p in batch:
        try:
            cur.execute(
                """INSERT INTO providers
                   (npi, entity_type, organization_name, last_name, first_name,
                    middle_name, credential, is_sole_proprietor, is_org_subpart,
                    parent_org_name, parent_org_tin, authorized_official_last,
                    authorized_official_first, authorized_official_phone,
                    enumeration_date, last_update_date, deactivation_date,
                    reactivation_date)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (npi) DO UPDATE SET
                    entity_type = EXCLUDED.entity_type,
                    organization_name = EXCLUDED.organization_name,
                    last_name = EXCLUDED.last_name,
                    first_name = EXCLUDED.first_name,
                    last_update_date = EXCLUDED.last_update_date""",
                p,
            )
        except Exception as e:
            log.debug("Provider insert error for NPI %s: %s", p[0], e)
            cur.connection.rollback()


def _flush_addresses(cur, batch):
    """Insert address batch."""
    for npi, purpose, addr in batch:
        try:
            cur.execute(
                """INSERT INTO addresses
                   (npi, address_purpose, street_line_1, street_line_2,
                    city, state_code, zip5, zip4, country_code, phone, fax,
                    street_number, street_name, street_suffix, unit_type, unit_number)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (npi, address_purpose) DO UPDATE SET
                    street_line_1 = EXCLUDED.street_line_1,
                    city = EXCLUDED.city,
                    state_code = EXCLUDED.state_code,
                    zip5 = EXCLUDED.zip5""",
                (
                    npi, purpose,
                    addr["street_line_1"], addr["street_line_2"],
                    addr["city"], addr["state_code"], addr["zip5"], addr["zip4"],
                    addr["country_code"], addr["phone"], addr["fax"],
                    addr["street_number"], addr["street_name"],
                    addr["street_suffix"], addr["unit_type"], addr["unit_number"],
                ),
            )
        except Exception as e:
            log.debug("Address insert error for NPI %s: %s", npi, e)
            cur.connection.rollback()


def _flush_taxonomies(cur, batch):
    """Insert taxonomy batch."""
    for t in batch:
        try:
            cur.execute(
                """INSERT INTO provider_taxonomies
                   (npi, taxonomy_code, license_number, license_state, is_primary)
                   VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (npi, taxonomy_code) DO UPDATE SET
                    is_primary = EXCLUDED.is_primary""",
                t,
            )
        except Exception as e:
            log.debug("Taxonomy insert error: %s", e)
            cur.connection.rollback()


def main():
    load_nppes()


if __name__ == "__main__":
    main()
