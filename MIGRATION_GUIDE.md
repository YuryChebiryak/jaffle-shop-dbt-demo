# Migration Guide: PostgreSQL to DuckDB + Apache Iceberg

This guide documents the migration from PostgreSQL to a modern data lakehouse architecture using DuckDB and Apache Iceberg.

## Architecture Changes

### Previous Architecture
- **Execution:** PostgreSQL
- **Storage:** PostgreSQL native tables
- **Query Layer:** Trino → PostgreSQL

### New Architecture
- **Execution:** DuckDB (local, in-process)
- **Storage:** Apache Iceberg (S3-compatible MinIO)
- **Query Layer:** Trino → Iceberg tables

## Prerequisites

1. **Python Environment**: Activate the virtual environment
   ```bash
   source .venv/bin/activate
   ```

2. **Install Dependencies**:
   ```bash
   uv pip install -r requirements.txt
   ```

3. **Podman**: Ensure Podman is installed and running

## Migration Steps

### Step 1: Start Infrastructure Services

Start MinIO (S3-compatible storage) and Trino:

```bash
podman-compose up -d minio minio-init
podman-compose up -d trino
```

Verify MinIO is running:
- MinIO Console: http://localhost:9001
- Credentials: minioadmin / minioadmin

### Step 2: Verify dbt Configuration

Test DuckDB connectivity:

```bash
.venv/bin/dbt debug --profiles-dir .
```

Expected output:
- ✅ Adapter type: duckdb
- ✅ Extensions: ['iceberg', 'httpfs']
- ✅ Connection test: OK

### Step 3: Load Seed Data

Load CSV files into Iceberg tables:

```bash
.venv/bin/dbt seed --profiles-dir .
```

This will create:
- `seeds.raw_customers`
- `seeds.raw_orders`
- `seeds.raw_payments`

Storage location: `s3://jaffle-iceberg-warehouse/jaffle_shop/seeds/`

### Step 4: Run Staging Models

Build staging layer:

```bash
.venv/bin/dbt run --profiles-dir . --select staging
```

This creates:
- `staging.stg_customers`
- `staging.stg_orders`
- `staging.stg_payments`

Note: Staging models are now tables (not views) for Iceberg compatibility.

### Step 5: Run Marts Models

Build marts layer:

```bash
.venv/bin/dbt run --profiles-dir . --select marts
```

This creates:
- `marts.customers`
- `marts.orders`

### Step 6: Run DDI Models

Build data-driven insights:

```bash
.venv/bin/dbt run --profiles-dir . --select ddi
```

This creates:
- `ddi.at_risk_customers`
- `ddi.rolling_30_day_orders`

### Step 7: Verify Trino Access

Test Trino connectivity to Iceberg:

```bash
podman exec -it trino trino
```

In Trino CLI:

```sql
-- Show catalogs
SHOW CATALOGS;

-- Show schemas
SHOW SCHEMAS FROM jaffle_iceberg;

-- List tables
SHOW TABLES FROM jaffle_iceberg.marts;

-- Query data
SELECT * FROM jaffle_iceberg.marts.customers LIMIT 10;
```

### Step 8: Update Superset Connections

If using Superset, update data source connections:

1. Navigate to: Data → Databases
2. Update connection string from:
   - Old: `trino://admin@trino:8080/jaffle_postgres`
   - New: `trino://admin@trino:8080/jaffle_iceberg`
3. Test connection
4. Update existing datasets to use new catalog

## Configuration Files Changed

### [`requirements.txt`](requirements.txt:1)
- Removed: `dbt-postgres`, `psycopg2-binary`
- Added: `dbt-duckdb>=1.8.0`

### [`profiles.yml`](profiles.yml:1)
- Changed adapter from `postgres` to `duckdb`
- Added Iceberg and httpfs extensions
- Configured S3-compatible storage (MinIO)
- Set Iceberg warehouse location

### [`dbt_project.yml`](dbt_project.yml:1)
- Added Iceberg metadata configuration
- Changed staging materialization from `view` to `table`

### [`docker-compose.yml`](docker-compose.yml:1)
- Added MinIO service for S3-compatible storage
- Added MinIO init service for bucket creation
- Updated Trino dependencies (removed PostgreSQL, added MinIO)
- Added Iceberg warehouse volume mount to Trino
- PostgreSQL retained only for Superset metadata

### [`trino/etc/catalog/jaffle_iceberg.properties`](trino/etc/catalog/jaffle_iceberg.properties:1)
- New Iceberg catalog configuration
- Filesystem-based catalog
- S3 endpoint pointing to MinIO

## Verification Commands

### Check DuckDB Database

```bash
.venv/bin/dbt ls --profiles-dir .
```

### Inspect Iceberg Metadata

```bash
# View snapshots
.venv/bin/dbt run-operation show_iceberg_snapshots --args '{table: "marts.customers"}'
```

### Query via Trino

```sql
-- View table properties
SELECT * FROM jaffle_iceberg.marts."customers$properties";

-- View table snapshots
SELECT * FROM jaffle_iceberg.marts."customers$snapshots";

-- View table files
SELECT * FROM jaffle_iceberg.marts."customers$files";
```

## Troubleshooting

### Issue: Cannot connect to MinIO

**Solution**: Ensure MinIO is running and accessible:

```bash
podman-compose ps
curl http://localhost:9000/minio/health/live
```

### Issue: Iceberg extension not loading

**Solution**: Install DuckDB extensions manually:

```bash
.venv/bin/python -c "import duckdb; conn = duckdb.connect(); conn.execute('INSTALL iceberg'); conn.execute('INSTALL httpfs');"
```

### Issue: Trino cannot read Iceberg tables

**Solution**: Verify catalog configuration and restart Trino:

```bash
podman-compose restart trino
podman-compose logs trino
```

### Issue: S3 connection errors

**Solution**: Check MinIO credentials in `profiles.yml` and `jaffle_iceberg.properties` match:
- Access Key: `minioadmin`
- Secret Key: `minioadmin`
- Endpoint: `localhost:9000` (host) or `minio:9000` (container)

## Rollback Procedure

If migration issues occur:

1. **Stop new services**:
   ```bash
   podman-compose down minio trino
   ```

2. **Restore `profiles.yml`**:
   ```bash
   git checkout profiles.yml
   ```

3. **Restore `requirements.txt`**:
   ```bash
   git checkout requirements.txt
   uv pip install -r requirements.txt
   ```

4. **Start PostgreSQL**:
   ```bash
   podman-compose up -d postgres trino
   ```

5. **Run dbt with PostgreSQL**:
   ```bash
   dbt seed
   dbt run
   ```

## Performance Considerations

### DuckDB Benefits
- In-process execution (no network overhead)
- Columnar storage (optimized for analytics)
- Parallel query execution

### Iceberg Benefits
- Partition pruning for large datasets
- Schema evolution without table rewrites
- Time travel for historical queries
- ACID transactions

## Next Steps

1. **Optimize Partitioning**: Add partition keys to large tables
2. **Enable Incremental Models**: Use Iceberg merge capabilities
3. **Configure Snapshot Retention**: Set retention policies
4. **Add Data Quality Tests**: Implement dbt tests
5. **Set Up CI/CD**: Automate deployment pipeline

## Resources

- [dbt-duckdb Documentation](https://github.com/duckdb/dbt-duckdb)
- [Apache Iceberg Documentation](https://iceberg.apache.org/)
- [DuckDB Iceberg Extension](https://duckdb.org/docs/extensions/iceberg)
- [Trino Iceberg Connector](https://trino.io/docs/current/connector/iceberg.html)
