#!/usr/bin/env perl
# =============================================================
# Database Transfer Tool — Medicaid Provider Spending (Perl)
# =============================================================
# Transfers all tables, materialized views, indexes, and
# constraints from a source PostgreSQL (Render) to a target
# PostgreSQL (AWS / local server).
#
# Prerequisites:
#   cpan DBD::Pg
#   # or: apt-get install libdbd-pg-perl
#   # or: yum install perl-DBD-Pg
#
# Usage:
#   perl etl/transfer_db.pl
#
#   # With environment variables:
#   SOURCE_DATABASE_URL="postgresql://user:pass@host/db?sslmode=require" \
#   TARGET_DATABASE_URL="postgresql://user:pass@host/db" \
#   perl etl/transfer_db.pl
#
#   # With command-line arguments:
#   perl etl/transfer_db.pl \
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
#   perl etl/transfer_db.pl --resume
#
#   # Transfer only specific tables:
#   perl etl/transfer_db.pl --tables spending,providers
# =============================================================

use strict;
use warnings;
use DBI;
use Getopt::Long;
use POSIX qw(strftime);
use Term::ReadKey;
use Time::HiRes qw(time);

my $BATCH_SIZE = 50_000;

my @BASE_TABLES = qw(
    providers
    hcpcs_codes
    addresses
    provider_taxonomies
    spending
);

my @MATERIALIZED_VIEWS = qw(
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
);

# ── Logging ──────────────────────────────────────────────────────

sub log_info  { printf STDERR "%s [INFO] %s\n",  strftime("%Y-%m-%d %H:%M:%S", localtime), $_[0]; }
sub log_error { printf STDERR "%s [ERROR] %s\n", strftime("%Y-%m-%d %H:%M:%S", localtime), $_[0]; }
sub log_warn  { printf STDERR "%s [WARN] %s\n",  strftime("%Y-%m-%d %H:%M:%S", localtime), $_[0]; }

# ── Connection helpers ───────────────────────────────────────────

sub prompt_connection {
    my ($label) = @_;
    print "\n" . ("=" x 50) . "\n";
    print "  $label Database Connection\n";
    print ("=" x 50) . "\n";

    print "  Host [localhost]: ";
    chomp(my $host = <STDIN>);
    $host ||= "localhost";

    print "  Port [5432]: ";
    chomp(my $port = <STDIN>);
    $port ||= "5432";

    print "  Database [medicaid_db]: ";
    chomp(my $db = <STDIN>);
    $db ||= "medicaid_db";

    print "  Username [postgres]: ";
    chomp(my $user = <STDIN>);
    $user ||= "postgres";

    print "  Password: ";
    ReadMode('noecho');
    chomp(my $pass = <STDIN>);
    ReadMode('restore');
    print "\n";

    my $ssl = ($host =~ /render\.com/) ? "require" : "prefer";
    return "postgresql://$user:$pass\@$host:$port/$db?sslmode=$ssl";
}

sub parse_url_to_dbi {
    my ($url) = @_;
    # Parse: postgresql://user:pass@host:port/db?sslmode=X
    if ($url =~ m{^postgresql://([^:]+):([^@]+)\@([^:/]+):?(\d+)?/([^?]+)(?:\?sslmode=(\w+))?}) {
        my ($user, $pass, $host, $port, $db, $ssl) = ($1, $2, $3, $4 || 5432, $5, $6 || "prefer");
        my $dsn = "dbi:Pg:dbname=$db;host=$host;port=$port;sslmode=$ssl";
        return ($dsn, $user, $pass);
    }
    die "Cannot parse connection URL: $url\n";
}

sub connect_db {
    my ($url, $readonly) = @_;
    my ($dsn, $user, $pass) = parse_url_to_dbi($url);
    my $dbh = DBI->connect($dsn, $user, $pass, {
        RaiseError => 1,
        AutoCommit => 1,
        pg_enable_utf8 => 1,
    }) or die "Connection failed: $DBI::errstr\n";
    return $dbh;
}

# ── Query helpers ────────────────────────────────────────────────

sub row_count {
    my ($dbh, $table) = @_;
    my ($count) = $dbh->selectrow_array("SELECT count(*) FROM $table");
    return $count;
}

sub table_exists {
    my ($dbh, $table) = @_;
    my ($exists) = $dbh->selectrow_array(
        "SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON c.relnamespace = n.oid WHERE c.relname = ? AND n.nspname = 'public')",
        undef, $table
    );
    return $exists;
}

sub get_columns {
    my ($dbh, $table) = @_;
    my $sth = $dbh->prepare(
        "SELECT column_name FROM information_schema.columns WHERE table_name = ? AND table_schema = 'public' ORDER BY ordinal_position"
    );
    $sth->execute($table);
    my @cols;
    while (my ($col) = $sth->fetchrow_array) { push @cols, $col; }

    # Fall back to pg_attribute for matviews
    unless (@cols) {
        $sth = $dbh->prepare(
            "SELECT a.attname FROM pg_attribute a JOIN pg_class c ON a.attrelid = c.oid JOIN pg_namespace n ON c.relnamespace = n.oid WHERE c.relname = ? AND n.nspname = 'public' AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum"
        );
        $sth->execute($table);
        while (my ($col) = $sth->fetchrow_array) { push @cols, $col; }
    }
    return @cols;
}

sub get_column_defs {
    my ($dbh, $table) = @_;
    my $sth = $dbh->prepare(
        "SELECT a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod), CASE WHEN a.attnotnull THEN 'NOT NULL' ELSE '' END FROM pg_attribute a JOIN pg_class c ON a.attrelid = c.oid JOIN pg_namespace n ON c.relnamespace = n.oid WHERE c.relname = ? AND n.nspname = 'public' AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum"
    );
    $sth->execute($table);
    my @defs;
    while (my @row = $sth->fetchrow_array) { push @defs, \@row; }
    return @defs;
}

# ── Schema creation ──────────────────────────────────────────────

sub create_target_table {
    my ($src, $tgt, $table) = @_;
    my @col_defs = get_column_defs($src, $table);
    die "No columns found for $table" unless @col_defs;

    my @cols_sql;
    for my $def (@col_defs) {
        my ($name, $dtype, $nn) = @$def;
        my $line = "    $name $dtype";
        $line .= " $nn" if $nn;
        push @cols_sql, $line;
    }
    my $create = "CREATE TABLE IF NOT EXISTS $table (\n" . join(",\n", @cols_sql) . "\n)";

    $tgt->do("DROP TABLE IF EXISTS $table CASCADE");
    $tgt->do($create);
    log_info("Created table $table on target (" . scalar(@col_defs) . " columns)");
}

# ── Transfer ─────────────────────────────────────────────────────

sub escape_copy_val {
    my ($v) = @_;
    return "\\N" unless defined $v;
    $v =~ s/\\/\\\\/g;
    $v =~ s/\t/\\t/g;
    $v =~ s/\n/\\n/g;
    $v =~ s/\r/\\r/g;
    return $v;
}

sub transfer_table {
    my ($src, $tgt, $table, $resume) = @_;
    my @columns = get_columns($src, $table);
    return 0 unless @columns;

    my $source_count = row_count($src, $table);
    if ($source_count == 0) {
        log_info("Skipping $table - 0 rows in source");
        return 0;
    }

    if ($resume && table_exists($tgt, $table)) {
        my $target_count = row_count($tgt, $table);
        if ($target_count >= $source_count) {
            log_info("Skipping $table - already has $target_count rows (>= source $source_count)");
            return $target_count;
        }
    }

    create_target_table($src, $tgt, $table);
    my $col_list = join(", ", @columns);
    log_info("Transferring $table: $source_count rows ...");

    my $sth = $src->prepare("SELECT $col_list FROM $table");
    $sth->execute();

    my $rows_transferred = 0;
    my $batch_rows = 0;
    my @batch_buf;
    my $t0 = time();

    while (my @row = $sth->fetchrow_array) {
        my $line = join("\t", map { escape_copy_val($_) } @row);
        push @batch_buf, "$line\n";
        $batch_rows++;

        if ($batch_rows >= $BATCH_SIZE) {
            # Use COPY IN
            $tgt->do("COPY $table ($col_list) FROM STDIN");
            for my $line_data (@batch_buf) {
                $tgt->pg_putcopydata($line_data);
            }
            $tgt->pg_putcopyend();

            $rows_transferred += $batch_rows;
            my $elapsed = time() - $t0;
            my $rate = $elapsed > 0 ? int($rows_transferred / $elapsed) : 0;
            my $pct = sprintf("%.1f", ($rows_transferred / $source_count) * 100);
            log_info("  $table: $rows_transferred / $source_count ($pct%) - $rate rows/sec");

            @batch_buf = ();
            $batch_rows = 0;
        }
    }

    # Final batch
    if ($batch_rows > 0) {
        $tgt->do("COPY $table ($col_list) FROM STDIN");
        for my $line_data (@batch_buf) {
            $tgt->pg_putcopydata($line_data);
        }
        $tgt->pg_putcopyend();
        $rows_transferred += $batch_rows;
    }

    my $elapsed = time() - $t0;
    my $rate = $elapsed > 0 ? int($rows_transferred / $elapsed) : 0;
    log_info(sprintf("  $table: DONE - %d rows in %.1fs (%d rows/sec)", $rows_transferred, $elapsed, $rate));
    return $rows_transferred;
}

# ── Indexes & Constraints ────────────────────────────────────────

sub create_indexes_and_constraints {
    my ($src, $tgt, $table) = @_;
    my $created = 0;

    # Primary keys
    my $sth = $src->prepare(
        "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid JOIN pg_namespace n ON t.relnamespace = n.oid WHERE t.relname = ? AND n.nspname = 'public' AND c.contype = 'p'"
    );
    $sth->execute($table);
    while (my ($condef) = $sth->fetchrow_array) {
        eval { $tgt->do("ALTER TABLE $table ADD $condef"); };
        $created++ unless $@;
    }

    # Unique constraints
    $sth = $src->prepare(
        "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid JOIN pg_namespace n ON t.relnamespace = n.oid WHERE t.relname = ? AND n.nspname = 'public' AND c.contype = 'u'"
    );
    $sth->execute($table);
    while (my ($condef) = $sth->fetchrow_array) {
        eval { $tgt->do("ALTER TABLE $table ADD $condef"); };
        $created++ unless $@;
    }

    # All indexes
    $sth = $src->prepare("SELECT indexdef FROM pg_indexes WHERE tablename = ? AND schemaname = 'public'");
    $sth->execute($table);
    while (my ($indexdef) = $sth->fetchrow_array) {
        $indexdef =~ s/CREATE INDEX /CREATE INDEX IF NOT EXISTS /;
        $indexdef =~ s/CREATE UNIQUE INDEX /CREATE UNIQUE INDEX IF NOT EXISTS /;
        eval { $tgt->do($indexdef); };
        $created++ unless $@;
    }

    log_info("  Created $created indexes/constraints on $table") if $created;
}

sub create_foreign_keys {
    my ($src, $tgt) = @_;
    my $created = 0;

    my $sth = $src->prepare(
        "SELECT tc.table_name, pg_get_constraintdef(c.oid) AS condef, c.conname FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid JOIN pg_namespace n ON t.relnamespace = n.oid JOIN information_schema.table_constraints tc ON tc.constraint_name = c.conname AND tc.table_schema = 'public' WHERE n.nspname = 'public' AND c.contype = 'f' ORDER BY tc.table_name"
    );
    $sth->execute();
    while (my ($tbl, $condef, $conname) = $sth->fetchrow_array) {
        eval { $tgt->do("ALTER TABLE $tbl ADD CONSTRAINT $conname $condef"); };
        $created++ unless $@;
    }
    log_info("Created $created foreign key constraints") if $created;
}

# ── Main ─────────────────────────────────────────────────────────

sub main {
    my %opts = (
        source_port => 5432, target_port => 5432,
        source_db   => "medicaid_db", target_db => "medicaid_db",
        source_user => "medicaid_db_user", target_user => "postgres",
    );

    GetOptions(
        "source-url=s"   => \$opts{source_url},
        "source-host=s"  => \$opts{source_host},
        "source-port=i"  => \$opts{source_port},
        "source-db=s"    => \$opts{source_db},
        "source-user=s"  => \$opts{source_user},
        "source-pass=s"  => \$opts{source_pass},
        "target-url=s"   => \$opts{target_url},
        "target-host=s"  => \$opts{target_host},
        "target-port=i"  => \$opts{target_port},
        "target-db=s"    => \$opts{target_db},
        "target-user=s"  => \$opts{target_user},
        "target-pass=s"  => \$opts{target_pass},
        "tables=s"       => \$opts{tables},
        "no-views"       => \$opts{no_views},
        "resume"         => \$opts{resume},
    ) or die "Invalid options\n";

    # Resolve source URL
    my $source_url = $opts{source_url} || $ENV{SOURCE_DATABASE_URL} || $ENV{DATABASE_URL};
    unless ($source_url) {
        if ($opts{source_host}) {
            my $ssl = ($opts{source_host} =~ /render\.com/) ? "require" : "prefer";
            $source_url = "postgresql://$opts{source_user}:$opts{source_pass}\@$opts{source_host}:$opts{source_port}/$opts{source_db}?sslmode=$ssl";
        } else {
            $source_url = prompt_connection("SOURCE");
        }
    }

    # Resolve target URL
    my $target_url = $opts{target_url} || $ENV{TARGET_DATABASE_URL};
    unless ($target_url) {
        if ($opts{target_host}) {
            my $ssl = ($opts{target_host} =~ /^(localhost|127\.0\.0\.1)$/) ? "disable" : "prefer";
            $target_url = "postgresql://$opts{target_user}:$opts{target_pass}\@$opts{target_host}:$opts{target_port}/$opts{target_db}?sslmode=$ssl";
        } else {
            $target_url = prompt_connection("TARGET");
        }
    }

    my ($safe_src) = $source_url =~ /\@(.+)$/;
    my ($safe_tgt) = $target_url =~ /\@(.+)$/;
    log_info("Source: ...\@$safe_src");
    log_info("Target: ...\@$safe_tgt");

    my $src = connect_db($source_url, 1);
    my $tgt = connect_db($target_url, 0);

    my @tables_list = $opts{tables} ? split(/,/, $opts{tables}) : @BASE_TABLES;
    my @views_list  = $opts{no_views} ? () : ($opts{tables} ? split(/,/, $opts{tables}) : @MATERIALIZED_VIEWS);

    # Filter to valid names
    my %base_set = map { $_ => 1 } @BASE_TABLES;
    my %mv_set   = map { $_ => 1 } @MATERIALIZED_VIEWS;
    @tables_list = grep { $base_set{$_} } @tables_list;
    @views_list  = grep { $mv_set{$_} }   @views_list;

    my $total_rows = 0;
    my $t_start = time();

    for my $tbl (@tables_list, @views_list) {
        eval {
            my $rows = transfer_table($src, $tgt, $tbl, $opts{resume});
            $total_rows += $rows;
            create_indexes_and_constraints($src, $tgt, $tbl) if $rows > 0;
        };
        if ($@) {
            log_error("Failed to transfer $tbl: $@");
            die $@ unless $opts{resume};
        }
    }

    log_info("Creating foreign key constraints ...");
    create_foreign_keys($src, $tgt);

    my $elapsed = time() - $t_start;
    log_info("");
    log_info("=" x 60);
    log_info(sprintf("Transfer complete: %d total rows in %.1fs", $total_rows, $elapsed));
    log_info("=" x 60);

    $src->disconnect;
    $tgt->disconnect;
}

main();
