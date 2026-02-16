#!/usr/bin/env ruby
# frozen_string_literal: true

# =============================================================
# Database Transfer Tool — Medicaid Provider Spending (Ruby)
# =============================================================
# Transfers all tables, materialized views, indexes, and
# constraints from a source PostgreSQL (Render) to a target
# PostgreSQL (AWS / local server).
#
# Prerequisites:
#   gem install pg
#
# Usage:
#   ruby etl/transfer_db.rb
#
#   # With environment variables:
#   SOURCE_DATABASE_URL="postgresql://user:pass@host/db?sslmode=require" \
#   TARGET_DATABASE_URL="postgresql://user:pass@host/db" \
#   ruby etl/transfer_db.rb
#
#   # With command-line arguments:
#   ruby etl/transfer_db.rb \
#     --source-host dpg-xxx.render.com \
#     --source-db medicaid_db \
#     --source-user medicaid_db_user \
#     --source-pass SECRET \
#     --target-host localhost \
#     --target-db medicaid_db \
#     --target-user postgres \
#     --target-pass mypassword
#
#   # Resume (skip tables that already have data):
#   ruby etl/transfer_db.rb --resume
#
#   # Transfer only specific tables:
#   ruby etl/transfer_db.rb --tables spending,providers
# =============================================================

require "pg"
require "optparse"
require "io/console"
require "logger"

LOG = Logger.new($stderr)
LOG.formatter = proc { |sev, time, _, msg| "#{time.strftime('%Y-%m-%d %H:%M:%S')} [#{sev}] #{msg}\n" }

BATCH_SIZE = 50_000

BASE_TABLES = %w[
  providers
  hcpcs_codes
  addresses
  provider_taxonomies
  spending
].freeze

MATERIALIZED_VIEWS = %w[
  mv_top_organizations
  mv_shared_addresses
  mv_spending_growth
  mv_outlier_providers
  mv_geographic_concentration
  mv_billing_servicing_network
  mv_org_yoy_growth
  mv_address_clustering
  mv_rapid_ramp
  mv_fraud_risk_score
  mv_avg_claim_by_provider
  mv_official_network
].freeze

# ── Helpers ──────────────────────────────────────────────────────

def prompt_connection(label)
  puts "\n#{'=' * 50}"
  puts "  #{label} Database Connection"
  puts "#{'=' * 50}"

  print "  Host [localhost]: "
  host = $stdin.gets.chomp
  host = "localhost" if host.empty?

  print "  Port [5432]: "
  port = $stdin.gets.chomp
  port = "5432" if port.empty?

  print "  Database [medicaid_db]: "
  db = $stdin.gets.chomp
  db = "medicaid_db" if db.empty?

  print "  Username [postgres]: "
  user = $stdin.gets.chomp
  user = "postgres" if user.empty?

  print "  Password: "
  pass = $stdin.noecho(&:gets).chomp
  puts

  ssl = host.include?("render.com") ? "require" : "prefer"

  "postgresql://#{user}:#{pass}@#{host}:#{port}/#{db}?sslmode=#{ssl}"
end

def row_count(conn, table)
  conn.exec("SELECT count(*) FROM #{table}").first["count"].to_i
end

def table_exists?(conn, table)
  res = conn.exec_params(
    "SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON c.relnamespace = n.oid WHERE c.relname = $1 AND n.nspname = 'public')",
    [table]
  )
  res.first["exists"] == "t"
end

def get_columns(conn, table)
  # Try information_schema first (works for tables)
  res = conn.exec_params(
    "SELECT column_name FROM information_schema.columns WHERE table_name = $1 AND table_schema = 'public' ORDER BY ordinal_position",
    [table]
  )
  cols = res.map { |r| r["column_name"] }

  # Fall back to pg_attribute (works for matviews)
  if cols.empty?
    res = conn.exec_params(
      "SELECT a.attname FROM pg_attribute a JOIN pg_class c ON a.attrelid = c.oid JOIN pg_namespace n ON c.relnamespace = n.oid WHERE c.relname = $1 AND n.nspname = 'public' AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum",
      [table]
    )
    cols = res.map { |r| r["attname"] }
  end
  cols
end

def get_column_defs(conn, table)
  res = conn.exec_params(
    "SELECT a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod), CASE WHEN a.attnotnull THEN 'NOT NULL' ELSE '' END FROM pg_attribute a JOIN pg_class c ON a.attrelid = c.oid JOIN pg_namespace n ON c.relnamespace = n.oid WHERE c.relname = $1 AND n.nspname = 'public' AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum",
    [table]
  )
  res.map { |r| [r["attname"], r["format_type"], r["case"]] }
end

# ── Schema creation ──────────────────────────────────────────────

def create_target_table(src, tgt, table)
  col_defs = get_column_defs(src, table)
  raise "No columns found for #{table}" if col_defs.empty?

  cols_sql = col_defs.map { |name, dtype, nn| "    #{name} #{dtype} #{nn}".rstrip }.join(",\n")
  create_sql = "CREATE TABLE IF NOT EXISTS #{table} (\n#{cols_sql}\n)"

  tgt.exec("DROP TABLE IF EXISTS #{table} CASCADE")
  tgt.exec(create_sql)
  LOG.info("Created table #{table} on target (#{col_defs.size} columns)")
end

# ── Transfer ─────────────────────────────────────────────────────

def transfer_table(src, tgt, table, resume: false)
  columns = get_columns(src, table)
  return 0 if columns.empty?

  source_count = row_count(src, table)
  if source_count.zero?
    LOG.info("Skipping #{table} - 0 rows in source")
    return 0
  end

  if resume && table_exists?(tgt, table)
    target_count = row_count(tgt, table)
    if target_count >= source_count
      LOG.info("Skipping #{table} - already has #{target_count} rows (>= source #{source_count})")
      return target_count
    end
  end

  create_target_table(src, tgt, table)
  col_list = columns.join(", ")
  LOG.info("Transferring #{table}: #{source_count} rows ...")

  # Use COPY for speed: COPY OUT from source, COPY IN to target
  rows_transferred = 0
  buf = StringIO.new
  batch_rows = 0
  t0 = Time.now

  # Declare a server-side cursor
  src.exec("DECLARE transfer_cur CURSOR FOR SELECT #{col_list} FROM #{table}")

  loop do
    res = src.exec("FETCH #{BATCH_SIZE} FROM transfer_cur")
    break if res.ntuples.zero?

    buf.truncate(0)
    buf.rewind

    res.each do |row|
      vals = columns.map do |c|
        v = row[c]
        v.nil? ? "\\N" : v.gsub("\\", "\\\\\\\\").gsub("\t", "\\t").gsub("\n", "\\n").gsub("\r", "\\r")
      end
      buf.puts(vals.join("\t"))
    end

    buf.rewind
    tgt.copy_data("COPY #{table} (#{col_list}) FROM STDIN") do
      while (line = buf.gets)
        tgt.put_copy_data(line)
      end
    end

    batch_rows = res.ntuples
    rows_transferred += batch_rows

    elapsed = Time.now - t0
    rate = elapsed > 0 ? (rows_transferred / elapsed).to_i : 0
    pct = (rows_transferred.to_f / source_count * 100).round(1)
    LOG.info("  #{table}: #{rows_transferred} / #{source_count} (#{pct}%) - #{rate} rows/sec")
  end

  src.exec("CLOSE transfer_cur")
  elapsed = Time.now - t0
  rate = elapsed > 0 ? (rows_transferred / elapsed).to_i : 0
  LOG.info("  #{table}: DONE - #{rows_transferred} rows in #{elapsed.round(1)}s (#{rate} rows/sec)")
  rows_transferred
end

# ── Indexes & Constraints ────────────────────────────────────────

def create_indexes_and_constraints(src, tgt, table)
  created = 0

  # Primary keys
  src.exec_params(
    "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid JOIN pg_namespace n ON t.relnamespace = n.oid WHERE t.relname = $1 AND n.nspname = 'public' AND c.contype = 'p'",
    [table]
  ).each do |r|
    tgt.exec("ALTER TABLE #{table} ADD #{r['pg_get_constraintdef']}") rescue nil
    created += 1
  end

  # Unique constraints
  src.exec_params(
    "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid JOIN pg_namespace n ON t.relnamespace = n.oid WHERE t.relname = $1 AND n.nspname = 'public' AND c.contype = 'u'",
    [table]
  ).each do |r|
    tgt.exec("ALTER TABLE #{table} ADD #{r['pg_get_constraintdef']}") rescue nil
    created += 1
  end

  # All indexes
  src.exec_params(
    "SELECT indexdef FROM pg_indexes WHERE tablename = $1 AND schemaname = 'public'",
    [table]
  ).each do |r|
    sql = r["indexdef"].gsub("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ").gsub("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS ")
    tgt.exec(sql) rescue nil
    created += 1
  end

  LOG.info("  Created #{created} indexes/constraints on #{table}") if created > 0
end

def create_foreign_keys(src, tgt)
  created = 0
  src.exec(
    "SELECT tc.table_name, pg_get_constraintdef(c.oid) AS condef, c.conname FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid JOIN pg_namespace n ON t.relnamespace = n.oid JOIN information_schema.table_constraints tc ON tc.constraint_name = c.conname AND tc.table_schema = 'public' WHERE n.nspname = 'public' AND c.contype = 'f' ORDER BY tc.table_name"
  ).each do |r|
    tgt.exec("ALTER TABLE #{r['table_name']} ADD CONSTRAINT #{r['conname']} #{r['condef']}") rescue nil
    created += 1
  end
  LOG.info("Created #{created} foreign key constraints") if created > 0
end

# ── Main ─────────────────────────────────────────────────────────

def main
  options = { resume: false, no_views: false }

  OptionParser.new do |opts|
    opts.banner = "Usage: ruby transfer_db.rb [options]"
    opts.on("--source-url URL")    { |v| options[:source_url] = v }
    opts.on("--source-host HOST")  { |v| options[:source_host] = v }
    opts.on("--source-port PORT")  { |v| options[:source_port] = v }
    opts.on("--source-db DB")      { |v| options[:source_db] = v }
    opts.on("--source-user USER")  { |v| options[:source_user] = v }
    opts.on("--source-pass PASS")  { |v| options[:source_pass] = v }
    opts.on("--target-url URL")    { |v| options[:target_url] = v }
    opts.on("--target-host HOST")  { |v| options[:target_host] = v }
    opts.on("--target-port PORT")  { |v| options[:target_port] = v }
    opts.on("--target-db DB")      { |v| options[:target_db] = v }
    opts.on("--target-user USER")  { |v| options[:target_user] = v }
    opts.on("--target-pass PASS")  { |v| options[:target_pass] = v }
    opts.on("--tables TABLES")     { |v| options[:tables] = v.split(",") }
    opts.on("--no-views")          { options[:no_views] = true }
    opts.on("--resume")            { options[:resume] = true }
  end.parse!

  # Resolve source URL
  source_url = options[:source_url] || ENV["SOURCE_DATABASE_URL"] || ENV["DATABASE_URL"]
  unless source_url
    if options[:source_host]
      ssl = options[:source_host].include?("render.com") ? "require" : "prefer"
      source_url = "postgresql://#{options[:source_user] || 'medicaid_db_user'}:#{options[:source_pass]}@#{options[:source_host]}:#{options[:source_port] || '5432'}/#{options[:source_db] || 'medicaid_db'}?sslmode=#{ssl}"
    else
      source_url = prompt_connection("SOURCE")
    end
  end

  # Resolve target URL
  target_url = options[:target_url] || ENV["TARGET_DATABASE_URL"]
  unless target_url
    if options[:target_host]
      ssl = %w[localhost 127.0.0.1].include?(options[:target_host]) ? "disable" : "prefer"
      target_url = "postgresql://#{options[:target_user] || 'postgres'}:#{options[:target_pass]}@#{options[:target_host]}:#{options[:target_port] || '5432'}/#{options[:target_db] || 'medicaid_db'}?sslmode=#{ssl}"
    else
      target_url = prompt_connection("TARGET")
    end
  end

  safe_src = source_url.split("@").last
  safe_tgt = target_url.split("@").last
  LOG.info("Source: ...@#{safe_src}")
  LOG.info("Target: ...@#{safe_tgt}")

  src = PG.connect(source_url)
  src.exec("SET default_transaction_read_only = on")
  tgt = PG.connect(target_url)

  tables = options[:tables] || BASE_TABLES
  views  = options[:no_views] ? [] : (options[:tables] || MATERIALIZED_VIEWS)
  total_rows = 0
  t_start = Time.now

  (tables.select { |t| BASE_TABLES.include?(t) } + views.select { |v| MATERIALIZED_VIEWS.include?(v) }).each do |tbl|
    begin
      src.exec("BEGIN")
      rows = transfer_table(src, tgt, tbl, resume: options[:resume])
      src.exec("COMMIT")
      total_rows += rows
      create_indexes_and_constraints(src, tgt, tbl) if rows > 0
    rescue => e
      LOG.error("Failed to transfer #{tbl}: #{e.message}")
      src.exec("ROLLBACK") rescue nil
      raise unless options[:resume]
    end
  end

  LOG.info("Creating foreign key constraints ...")
  create_foreign_keys(src, tgt)

  elapsed = Time.now - t_start
  LOG.info("\n#{'=' * 60}")
  LOG.info("Transfer complete: #{total_rows} total rows in #{elapsed.round(1)}s")
  LOG.info("#{'=' * 60}")

  src.close
  tgt.close
end

main
