"""Refresh all materialized views for the Medicaid Provider Spending dashboard."""

import logging
import os
import sys

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

MATERIALIZED_VIEWS = [
    "mv_provider_spending_summary",
    "mv_monthly_spending",
    "mv_state_spending",
    "mv_hcpcs_spending",
    # Analysis views
    "mv_top_organizations",
    "mv_shared_addresses",
    "mv_spending_growth",
    "mv_outlier_providers",
    "mv_geographic_concentration",
    "mv_billing_servicing_network",
]


def refresh_views(database_url: str | None = None, concurrently: bool = False):
    """Refresh all materialized views."""
    database_url = database_url or os.environ["DATABASE_URL"]
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    cur = conn.cursor()

    log.info("=== Refreshing materialized views ===")

    for view_name in MATERIALIZED_VIEWS:
        try:
            if concurrently:
                cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}")
            else:
                cur.execute(f"REFRESH MATERIALIZED VIEW {view_name}")
            log.info("Refreshed %s", view_name)
        except Exception as e:
            log.error("Failed to refresh %s: %s", view_name, e)

    # Report row counts
    for view_name in MATERIALIZED_VIEWS:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {view_name}")
            count = cur.fetchone()[0]
            log.info("  %s: %d rows", view_name, count)
        except Exception as e:
            log.error("  %s: count failed — %s", view_name, e)

    cur.close()
    conn.close()
    log.info("=== View refresh complete ===")


def main():
    concurrently = "--concurrently" in sys.argv
    refresh_views(concurrently=concurrently)


if __name__ == "__main__":
    main()
