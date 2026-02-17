# Provider Data Exports

Export tools for migrating provider data to a separate MySQL database.

## Files

| File | Description |
|------|-------------|
| `mysql_schema.sql` | MySQL CREATE TABLE statements + LOAD DATA commands |
| `export_provider_data.py` | Python script to export all tables from PostgreSQL to CSV |

## How to Export

1. **Generate CSV files** (requires `DATABASE_URL` pointing to the PostgreSQL source):

```bash
DATABASE_URL="postgresql://..." python exports/export_provider_data.py
```

This creates 5 CSV files in this directory:

| CSV File | Rows | Size |
|----------|------|------|
| `providers.csv` | 9,034,519 | ~663 MB |
| `addresses.csv` | 18,069,038 | ~1.5 GB |
| `provider_taxonomies.csv` | 11,009,297 | ~345 MB |
| `taxonomy_codes.csv` | 883 | ~392 KB |
| `hcpcs_codes.csv` | 21,358 | ~1.6 MB |

## How to Import into MySQL

1. **Create the database and tables:**

```bash
mysql -u root -p -e "CREATE DATABASE medicaid_providers CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p medicaid_providers < exports/mysql_schema.sql
```

2. **Load the CSV data** (uncomment the LOAD DATA commands at the bottom of `mysql_schema.sql`, or run them manually):

```bash
mysql --local-infile=1 -u root -p medicaid_providers
```

Then in MySQL:
```sql
SET GLOBAL local_infile = 1;

-- Load in this order (foreign key dependencies):
-- 1. providers
-- 2. taxonomy_codes, hcpcs_codes
-- 3. addresses, provider_taxonomies
-- (See LOAD DATA commands in mysql_schema.sql)
```

## Notes

- CSV files are excluded from git (too large). Run the export script to generate them.
- The MySQL schema uses InnoDB with utf8mb4 encoding.
- Boolean fields are stored as TINYINT(1) in MySQL (0/1 in CSV).
- Empty CSV fields map to NULL in MySQL via the LOAD DATA SET clauses.
