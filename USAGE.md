# DuckDB dbt Usage Guide

## Quick Start

The project has been migrated from PostgreSQL to DuckDB. Here's how to run dbt commands:

### Option 1: Using the Helper Script (Recommended)

```bash
./run_dbt.sh build
./run_dbt.sh run
./run_dbt.sh test
./run_dbt.sh debug
```

### Option 2: Using the Project's Virtual Environment Directly

```bash
# Use the project's .venv dbt directly
.venv/bin/dbt build --profiles-dir .
.venv/bin/dbt run --profiles-dir .
.venv/bin/dbt test --profiles-dir .
```

### Option 3: Activate Virtual Environment First

```bash
# Deactivate any other venv first
deactivate

# Activate the project's .venv
source .venv/bin/activate

# Now run dbt commands
dbt build --profiles-dir .
dbt run --profiles-dir .
dbt test --profiles-dir .

# When done
deactivate
```

## Why You Get "Could not find adapter type duckdb" Error

If you see this error:
```
Credentials in profile "jaffle_shop", target "dev" invalid: Runtime Error
  Could not find adapter type duckdb!
```

**Cause:** You have a different Python virtual environment activated (like `venv` instead of `.venv`) that doesn't have `dbt-duckdb` installed.

**Solution:** Use one of the three methods above to ensure you're using the project's `.venv` directory.

## Verify Your Environment

Check which dbt you're using:

```bash
which dbt
# Should show: /Users/yury/jaffle-shop-dbt-demo/.venv/bin/dbt

dbt --version
# Should show: duckdb: 1.8.0
```

If you see a different path or don't see duckdb adapter, you're using the wrong environment.

## Common Commands

```bash
# Full build (clean, seeds, models, tests)
./run_dbt.sh build

# Run only models
./run_dbt.sh run

# Run only tests
./run_dbt.sh test

# Load seed data
./run_dbt.sh seed

# Clean generated files
./run_dbt.sh clean

# Debug connection
./run_dbt.sh debug

# Run specific model
./run_dbt.sh run --select customers

# Run specific layer
./run_dbt.sh run --select marts
./run_dbt.sh run --select staging
```

## Database Location

DuckDB database file: `./data/duckdb/jaffle_shop.db`

## Verify Data

Run the verification script:

```bash
.venv/bin/python verify_duckdb.py
```

This will show:
- All tables created
- Row counts by layer
- Sample data from marts and DDI tables

## Troubleshooting

### Problem: Wrong venv activated

```bash
# Check current Python
which python
# If it shows something other than .venv, deactivate and use the helper script

deactivate
./run_dbt.sh debug
```

### Problem: Missing dbt-duckdb

```bash
# Install dependencies in the project's .venv
.venv/bin/pip install -r requirements.txt

# Or using uv
uv pip install -r requirements.txt
```

### Problem: Database locked

```bash
# If DuckDB database is locked, ensure no other processes are using it
rm ./data/duckdb/jaffle_shop.db*
./run_dbt.sh build
```

## Expected Results

After running `./run_dbt.sh build`, you should see:

```
Done. PASS=59 WARN=0 ERROR=0 SKIP=0 NO-OP=1 TOTAL=60
```

**Data Counts:**
- Seeds: 100 customers, 99 orders, 113 payments
- Staging: 100 customers, 99 orders, 113 payments
- Marts: 100 customers, 99 orders
- DDI: 14 at-risk customers, 48 rolling 30-day records

## Infrastructure

### MinIO (S3 Storage)

```bash
# Start MinIO
podman compose up -d minio

# Access MinIO Console
open http://localhost:9001
# Login: minioadmin / minioadmin
```

### Verification

```bash
# Check services
podman compose ps

# View MinIO logs
podman compose logs minio

# Stop all services
podman compose down
```

## Migration from PostgreSQL

This project was migrated from PostgreSQL to DuckDB. Key changes:

1. **Adapter:** `dbt-postgres` → `dbt-duckdb`
2. **Database:** PostgreSQL server → DuckDB file
3. **Staging:** Views changed to tables (DuckDB requirement)
4. **Data Types:** Some types adjusted for DuckDB compatibility

See [`MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md) for complete migration details.

## Next Steps

1. **Run dbt build:** `./run_dbt.sh build`
2. **Verify data:** `.venv/bin/python verify_duckdb.py`
3. **Query data:** Use DBeaver or similar tool to connect to `./data/duckdb/jaffle_shop.db`

## Documentation

- **Architecture:** [`plans/duckdb-iceberg-migration-architecture.md`](plans/duckdb-iceberg-migration-architecture.md)
- **Migration Guide:** [`MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md)
- **Implementation Summary:** [`IMPLEMENTATION_SUMMARY.md`](IMPLEMENTATION_SUMMARY.md)
