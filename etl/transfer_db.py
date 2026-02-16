#!/usr/bin/env python3
"""
Database Transfer Tool — Medicaid Provider Spending
=====================================================
Transfers all tables and materialized views from a source PostgreSQL
database (e.g. Render) to a target PostgreSQL database (e.g. local server).

Usage:
    python -m etl.transfer_db

    # Or pass connection details via arguments:
    python -m etl.transfer_db \
        --source-host dpg-xxx.ohio-postgres.render.com \
        --source-db medicaid_db \
        --source-user medicaid_db_user \
        --source-pass SECRET \
        --target-host localhost \
        --target-db medicaid_db \
        --target-user postgres \
        --target-pass mypassword

    # Or via environment variables:
    SOURCE_DATABASE_URL="postgresql://user:pass@host/db" \
    TARGET_DATABASE_URL="postgresql://user:pass@host/db" \
    python -m etl.transfer_db

    # Transfer only specific tables:
    python -m etl.transfer_db --tables spending,providers

    # Resume a failed transfer (skip tables already populated):
    python -m etl.transfer_db --resume
"""

import argparse
import io
import logging
import os
import sys
import time
from getpass import getpass

import psycopg2
import psycopg2.extras

# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────
# [EN] Tables in dependency order (parents before children)
# [RU] Таблицы в порядке зависимостей (родительские перед дочерними)
# [PT] Tabelas em ordem de dependencia (pais antes de filhos)
BASE_TABLES = [
    "providers",
    "hcpcs_codes",
    "addresses",
    "provider_taxonomies",
    "spending",
]

# [EN] Materialized views to transfer as regular tables
# [RU] Материализованные представления для переноса как обычные таблицы
# [PT] Views materializadas para transferir como tabelas regulares
MATERIALIZED_VIEWS = [
    "mv_top_organizations",
    "mv_shared_addresses",
    "mv_spending_growth",
    "mv_outlier_providers",
    "mv_geographic_concentration",
    "mv_billing_servicing_network",
    "mv_org_yoy_growth",
    "mv_address_clustering",
    "mv_rapid_ramp",
    "mv_fraud_risk_score",
    "mv_avg_claim_by_provider",
    "mv_official_network",
]

BATCH_SIZE = 50_000


def get_connection_from_prompt(label: str) -> str:
    """Prompt user for connection details interactively."""
    print(f"\n{'='*50}")
    print(f"  {label} Database Connection")
    print(f"{'='*50}")
    host = input(f"  Host [localhost]: ").strip() or "localhost"
    port = input(f"  Port [5432]: ").strip() or "5432"
    dbname = input(f"  Database [medicaid_db]: ").strip() or "medicaid_db"
    user = input(f"  Username [postgres]: ").strip() or "postgres"
    password = getpass(f"  Password: ")
    sslmode = input(f"  SSL mode [require]: ").strip() or "require"
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}?sslmode={sslmode}"


def get_source_url(args) -> str:
    """Resolve source database URL from args, env, or prompt."""
    if args.source_url:
        return args.source_url
    if os.environ.get("SOURCE_DATABASE_URL"):
        return os.environ["SOURCE_DATABASE_URL"]
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    if args.source_host:
        sslmode = "require" if "render.com" in args.source_host else "prefer"
        return (
            f"postgresql://{args.source_user}:{args.source_pass}"
            f"@{args.source_host}:{args.source_port}/{args.source_db}"
            f"?sslmode={sslmode}"
        )
    return get_connection_from_prompt("SOURCE")


def get_target_url(args) -> str:
    """Resolve target database URL from args, env, or prompt."""
    if args.target_url:
        return args.target_url
    if os.environ.get("TARGET_DATABASE_URL"):
        return os.environ["TARGET_DATABASE_URL"]
    if args.target_host:
        sslmode = "disable" if args.target_host in ("localhost", "127.0.0.1") else "prefer"
        return (
            f"postgresql://{args.target_user}:{args.target_pass}"
            f"@{args.target_host}:{args.target_port}/{args.target_db}"
            f"?sslmode={sslmode}"
        )
    return get_connection_from_prompt("TARGET")


def get_table_columns(conn, table_name: str) -> list[str]:
    """Get column names for a table or materialized view."""
    cur = conn.cursor()
    # Works for both regular tables and materialized views
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
        ORDER BY ordinal_position
    """, (table_name,))
    cols = [r[0] for r in cur.fetchall()]

    # information_schema doesn't list matview columns; fall back to pg_attribute
    if not cols:
        cur.execute("""
            SELECT a.attname
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            JOIN pg_namespace n ON c.relnamespace = n.oid
            WHERE c.relname = %s AND n.nspname = 'public'
              AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY a.attnum
        """, (table_name,))
        cols = [r[0] for r in cur.fetchall()]
    cur.close()
    return cols


def get_row_count(conn, table_name: str) -> int:
    """Get exact row count for a table."""
    cur = conn.cursor()
    cur.execute(f"SELECT count(*) FROM {table_name}")
    count = cur.fetchone()[0]
    cur.close()
    return count


def table_exists(conn, table_name: str) -> bool:
    """Check if a table exists in the target database."""
    cur = conn.cursor()
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM pg_class c
            JOIN pg_namespace n ON c.relnamespace = n.oid
            WHERE c.relname = %s AND n.nspname = 'public'
        )
    """, (table_name,))
    exists = cur.fetchone()[0]
    cur.close()
    return exists


def create_target_schema(source_conn, target_conn, table_name: str, columns: list[str]):
    """
    Create the target table using the source table's column types.
    Materialized views are created as regular tables on the target.
    """
    cur_src = source_conn.cursor()
    cur_tgt = target_conn.cursor()

    # Get column definitions from source
    cur_src.execute("""
        SELECT a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod),
               CASE WHEN a.attnotnull THEN 'NOT NULL' ELSE '' END
        FROM pg_attribute a
        JOIN pg_class c ON a.attrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE c.relname = %s AND n.nspname = 'public'
          AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY a.attnum
    """, (table_name,))
    col_defs = cur_src.fetchall()

    if not col_defs:
        raise ValueError(f"No columns found for {table_name} in source")

    # Build CREATE TABLE statement
    col_strs = []
    for name, dtype, nullable in col_defs:
        # Skip auto-generated serial columns for matviews being copied
        col_strs.append(f"    {name} {dtype} {nullable}".rstrip())

    create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
    create_sql += ",\n".join(col_strs)
    create_sql += "\n)"

    cur_tgt.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
    cur_tgt.execute(create_sql)
    target_conn.commit()

    cur_src.close()
    cur_tgt.close()
    log.info(f"Created table {table_name} on target ({len(col_defs)} columns)")


def transfer_table(source_conn, target_conn, table_name: str,
                    resume: bool = False) -> int:
    """
    Transfer a single table from source to target using COPY for speed.
    Returns the number of rows transferred.
    """
    columns = get_table_columns(source_conn, table_name)
    if not columns:
        log.warning(f"Skipping {table_name} — no columns found (empty or missing)")
        return 0

    source_count = get_row_count(source_conn, table_name)
    if source_count == 0:
        log.info(f"Skipping {table_name} — 0 rows in source")
        return 0

    # Check if target already has data (resume mode)
    if resume and table_exists(target_conn, table_name):
        target_count = get_row_count(target_conn, table_name)
        if target_count >= source_count:
            log.info(f"Skipping {table_name} — already has {target_count:,} rows (>= source {source_count:,})")
            return target_count

    # Create target table
    create_target_schema(source_conn, target_conn, table_name, columns)

    col_list = ", ".join(columns)
    log.info(f"Transferring {table_name}: {source_count:,} rows ...")

    # Use COPY OUT from source → pipe → COPY IN to target
    cur_src = source_conn.cursor("server_cursor_" + table_name)
    cur_src.itersize = BATCH_SIZE

    cur_tgt = target_conn.cursor()
    buf = io.StringIO()
    rows_transferred = 0
    batch_rows = 0
    t0 = time.time()

    cur_src.execute(f"SELECT {col_list} FROM {table_name}")

    for row in cur_src:
        # Write tab-separated values, escaping nulls
        vals = []
        for v in row:
            if v is None:
                vals.append("\\N")
            else:
                s = str(v).replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")
                vals.append(s)
        buf.write("\t".join(vals) + "\n")
        batch_rows += 1

        if batch_rows >= BATCH_SIZE:
            buf.seek(0)
            cur_tgt.copy_from(buf, table_name, columns=columns, null="\\N")
            target_conn.commit()
            rows_transferred += batch_rows
            elapsed = time.time() - t0
            rate = rows_transferred / elapsed if elapsed > 0 else 0
            pct = (rows_transferred / source_count) * 100
            log.info(
                f"  {table_name}: {rows_transferred:,} / {source_count:,} "
                f"({pct:.1f}%) — {rate:,.0f} rows/sec"
            )
            buf.close()
            buf = io.StringIO()
            batch_rows = 0

    # Final batch
    if batch_rows > 0:
        buf.seek(0)
        cur_tgt.copy_from(buf, table_name, columns=columns, null="\\N")
        target_conn.commit()
        rows_transferred += batch_rows
    buf.close()

    elapsed = time.time() - t0
    rate = rows_transferred / elapsed if elapsed > 0 else 0
    log.info(
        f"  {table_name}: DONE — {rows_transferred:,} rows in "
        f"{elapsed:.1f}s ({rate:,.0f} rows/sec)"
    )

    cur_src.close()
    cur_tgt.close()
    return rows_transferred


def create_indexes_and_constraints(target_conn, table_name: str, source_conn):
    """
    Copy ALL indexes (including primary keys, unique constraints)
    and foreign key constraints from source to target.
    """
    cur_src = source_conn.cursor()
    cur_tgt = target_conn.cursor()
    created = 0

    # ── Primary key constraints ─────────────────────────────────────
    cur_src.execute("""
        SELECT pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE t.relname = %s AND n.nspname = 'public'
          AND c.contype = 'p'
    """, (table_name,))
    for (condef,) in cur_src.fetchall():
        try:
            cur_tgt.execute(f"ALTER TABLE {table_name} ADD {condef}")
            target_conn.commit()
            created += 1
        except Exception as e:
            log.debug(f"  PK on {table_name}: {e}")
            target_conn.rollback()

    # ── Unique constraints ──────────────────────────────────────────
    cur_src.execute("""
        SELECT pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE t.relname = %s AND n.nspname = 'public'
          AND c.contype = 'u'
    """, (table_name,))
    for (condef,) in cur_src.fetchall():
        try:
            cur_tgt.execute(f"ALTER TABLE {table_name} ADD {condef}")
            target_conn.commit()
            created += 1
        except Exception as e:
            log.debug(f"  Unique on {table_name}: {e}")
            target_conn.rollback()

    # ── All indexes (non-constraint-backed) ─────────────────────────
    cur_src.execute("""
        SELECT indexdef FROM pg_indexes
        WHERE tablename = %s AND schemaname = 'public'
    """, (table_name,))
    for (indexdef,) in cur_src.fetchall():
        try:
            sql = indexdef.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ")
            sql = sql.replace("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS ")
            cur_tgt.execute(sql)
            target_conn.commit()
            created += 1
        except Exception as e:
            # Silently skip duplicates from constraint-backed indexes
            if "already exists" not in str(e):
                log.debug(f"  Index on {table_name}: {e}")
            target_conn.rollback()

    if created:
        log.info(f"  Created {created} indexes/constraints on {table_name}")

    cur_src.close()
    cur_tgt.close()


def create_foreign_keys(target_conn, source_conn):
    """
    Create all foreign key constraints after all tables are loaded.
    Done last so parent tables exist before children reference them.
    """
    cur_src = source_conn.cursor()
    cur_tgt = target_conn.cursor()
    created = 0

    cur_src.execute("""
        SELECT
            tc.table_name,
            pg_get_constraintdef(c.oid) AS condef,
            c.conname
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        JOIN information_schema.table_constraints tc
            ON tc.constraint_name = c.conname AND tc.table_schema = 'public'
        WHERE n.nspname = 'public' AND c.contype = 'f'
        ORDER BY tc.table_name
    """)
    fks = cur_src.fetchall()

    for tbl, condef, conname in fks:
        try:
            cur_tgt.execute(f"ALTER TABLE {tbl} ADD CONSTRAINT {conname} {condef}")
            target_conn.commit()
            created += 1
        except Exception as e:
            log.debug(f"  FK {conname} on {tbl}: {e}")
            target_conn.rollback()

    if created:
        log.info(f"Created {created} foreign key constraints")

    cur_src.close()
    cur_tgt.close()


def transfer_all(source_url: str, target_url: str,
                 tables: list[str] | None = None,
                 include_views: bool = True,
                 resume: bool = False):
    """
    Main transfer orchestrator.
    """
    # Determine which tables to transfer
    if tables:
        transfer_list = [t for t in tables if t in BASE_TABLES]
        view_list = [v for v in tables if v in MATERIALIZED_VIEWS]
    else:
        transfer_list = BASE_TABLES[:]
        view_list = MATERIALIZED_VIEWS[:] if include_views else []

    log.info(f"Connecting to source database ...")
    source_conn = psycopg2.connect(source_url)
    source_conn.set_session(readonly=True, autocommit=True)

    log.info(f"Connecting to target database ...")
    target_conn = psycopg2.connect(target_url)
    target_conn.set_session(autocommit=False)

    total_rows = 0
    t_start = time.time()

    # ── Transfer base tables ────────────────────────────────────────
    for tbl in transfer_list:
        try:
            rows = transfer_table(source_conn, target_conn, tbl, resume=resume)
            total_rows += rows
            if rows > 0:
                create_indexes_and_constraints(target_conn, tbl, source_conn)
        except Exception as e:
            log.error(f"Failed to transfer {tbl}: {e}")
            target_conn.rollback()
            if not resume:
                raise

    # ── Transfer materialized views (as tables) ─────────────────────
    for mv in view_list:
        try:
            rows = transfer_table(source_conn, target_conn, mv, resume=resume)
            total_rows += rows
            if rows > 0:
                create_indexes_and_constraints(target_conn, mv, source_conn)
        except Exception as e:
            log.error(f"Failed to transfer {mv}: {e}")
            target_conn.rollback()
            if not resume:
                raise

    # ── Foreign keys (last, after all parent tables exist) ────────
    log.info("Creating foreign key constraints ...")
    create_foreign_keys(target_conn, source_conn)

    elapsed = time.time() - t_start
    log.info(f"\n{'='*60}")
    log.info(f"Transfer complete: {total_rows:,} total rows in {elapsed:.1f}s")
    log.info(f"{'='*60}")

    source_conn.close()
    target_conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Transfer Medicaid Provider Spending database between PostgreSQL instances"
    )

    # Source connection
    src = parser.add_argument_group("Source database (Render)")
    src.add_argument("--source-url", help="Full source connection URL")
    src.add_argument("--source-host", help="Source host")
    src.add_argument("--source-port", default="5432", help="Source port (default: 5432)")
    src.add_argument("--source-db", default="medicaid_db", help="Source database name")
    src.add_argument("--source-user", default="medicaid_db_user", help="Source username")
    src.add_argument("--source-pass", default="", help="Source password")

    # Target connection
    tgt = parser.add_argument_group("Target database (local)")
    tgt.add_argument("--target-url", help="Full target connection URL")
    tgt.add_argument("--target-host", help="Target host")
    tgt.add_argument("--target-port", default="5432", help="Target port (default: 5432)")
    tgt.add_argument("--target-db", default="medicaid_db", help="Target database name")
    tgt.add_argument("--target-user", default="postgres", help="Target username")
    tgt.add_argument("--target-pass", default="", help="Target password")

    # Options
    parser.add_argument("--tables", help="Comma-separated list of tables to transfer (default: all)")
    parser.add_argument("--no-views", action="store_true", help="Skip materialized views")
    parser.add_argument("--resume", action="store_true", help="Skip tables that already have data on target")

    args = parser.parse_args()

    source_url = get_source_url(args)
    target_url = get_target_url(args)

    tables_list = args.tables.split(",") if args.tables else None

    # Mask passwords in log output
    safe_src = source_url.split("@")[-1] if "@" in source_url else source_url
    safe_tgt = target_url.split("@")[-1] if "@" in target_url else target_url
    log.info(f"Source: ...@{safe_src}")
    log.info(f"Target: ...@{safe_tgt}")

    transfer_all(
        source_url=source_url,
        target_url=target_url,
        tables=tables_list,
        include_views=not args.no_views,
        resume=args.resume,
    )


if __name__ == "__main__":
    main()
