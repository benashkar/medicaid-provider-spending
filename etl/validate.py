"""Post-load validation queries for Medicaid Provider Spending database."""

import logging
import os
import sys

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


VALIDATION_QUERIES = [
    (
        "Spending row count",
        "SELECT COUNT(*) FROM spending",
        lambda x: x > 0,
        "Spending table should have data",
    ),
    (
        "Provider count",
        "SELECT COUNT(*) FROM providers",
        lambda x: x > 0,
        "Providers table should have data",
    ),
    (
        "Address count",
        "SELECT COUNT(*) FROM addresses",
        lambda x: x > 0,
        "Addresses table should have data",
    ),
    (
        "Taxonomy count",
        "SELECT COUNT(*) FROM provider_taxonomies",
        lambda x: x > 0,
        "Taxonomies table should have data",
    ),
    (
        "HCPCS code count",
        "SELECT COUNT(*) FROM hcpcs_codes",
        lambda x: x > 0,
        "HCPCS codes table should have data",
    ),
    (
        "Spending date range",
        "SELECT MIN(claim_month), MAX(claim_month) FROM spending",
        None,
        "Show spending date range",
    ),
    (
        "Unique billing NPIs in spending",
        "SELECT COUNT(DISTINCT billing_npi) FROM spending",
        None,
        "Count of unique billing providers",
    ),
    (
        "Unique servicing NPIs in spending",
        "SELECT COUNT(DISTINCT servicing_npi) FROM spending",
        None,
        "Count of unique servicing providers",
    ),
    (
        "Total paid amount",
        "SELECT SUM(total_paid)::NUMERIC(20,2) FROM spending",
        lambda x: x > 0,
        "Total spending should be positive",
    ),
    (
        "Orphan billing NPIs (not in providers table)",
        """SELECT COUNT(DISTINCT s.billing_npi)
           FROM spending s
           LEFT JOIN providers p ON p.npi = s.billing_npi
           WHERE p.npi IS NULL""",
        None,
        "Billing NPIs missing from providers table",
    ),
    (
        "Orphan servicing NPIs (not in providers table)",
        """SELECT COUNT(DISTINCT s.servicing_npi)
           FROM spending s
           LEFT JOIN providers p ON p.npi = s.servicing_npi
           WHERE p.npi IS NULL""",
        None,
        "Servicing NPIs missing from providers table",
    ),
    (
        "Providers without practice address",
        """SELECT COUNT(*)
           FROM providers p
           LEFT JOIN addresses a ON a.npi = p.npi AND a.address_purpose = 'PRACTICE'
           WHERE a.address_id IS NULL""",
        None,
        "Providers missing practice address",
    ),
    (
        "Address parse rate (has street_number)",
        """SELECT
            ROUND(
                COUNT(CASE WHEN street_number IS NOT NULL THEN 1 END)::NUMERIC
                / NULLIF(COUNT(*), 0) * 100, 1
            )
           FROM addresses""",
        lambda x: x is not None and x >= 80,
        "At least 80% of addresses should have parsed street_number",
    ),
    (
        "State distribution (top 5)",
        """SELECT state_code, COUNT(*) AS cnt
           FROM addresses
           WHERE address_purpose = 'PRACTICE' AND state_code IS NOT NULL
           GROUP BY state_code
           ORDER BY cnt DESC
           LIMIT 5""",
        None,
        "Top 5 states by provider count",
    ),
]


def run_validations(database_url: str | None = None):
    """Run all validation queries and report results."""
    database_url = database_url or os.environ["DATABASE_URL"]
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    log.info("=== Running post-load validations ===")
    passed = 0
    failed = 0
    info_only = 0

    for name, query, check, description in VALIDATION_QUERIES:
        try:
            cur.execute(query)
            result = cur.fetchall()

            if len(result) == 1 and len(result[0]) == 1:
                value = result[0][0]
                display = str(value)
            else:
                display = str(result)
                value = result

            if check is not None:
                if check(result[0][0] if len(result) == 1 and len(result[0]) == 1 else result):
                    log.info("PASS  %-45s → %s", name, display)
                    passed += 1
                else:
                    log.warning("FAIL  %-45s → %s  (%s)", name, display, description)
                    failed += 1
            else:
                log.info("INFO  %-45s → %s", name, display)
                info_only += 1

        except Exception as e:
            log.error("ERROR %-45s → %s", name, e)
            conn.rollback()
            failed += 1

    cur.close()
    conn.close()

    log.info("=== Validation summary ===")
    log.info("Passed: %d | Failed: %d | Info: %d", passed, failed, info_only)

    if failed > 0:
        log.warning("Some validations failed — review output above")
        return False
    return True


def main():
    success = run_validations()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
