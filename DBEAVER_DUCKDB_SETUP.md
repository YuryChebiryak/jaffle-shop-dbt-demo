# DBeaver Setup Guide - DuckDB Connection

Since the project has migrated to DuckDB, you should connect directly to the DuckDB database file (not via Trino/Iceberg, as those tables are standard DuckDB tables, not Iceberg format).

## Option 1: Direct DuckDB Connection (Recommended)

### Prerequisites

1. DBeaver Community or Enterprise Edition installed
2. DuckDB JDBC driver (DBeaver can auto-install)

### Connection Steps

1. **Open DBeaver** → Database → New Database Connection

2. **Select DuckDB:**
   - Search for "DuckDB" in the driver list
   - If not found, DBeaver will offer to download the driver
   - Click "Download/Update" if needed

3. **Configure Connection:**
   - **Path:** `/Users/yury/jaffle-shop-dbt-demo/data/duckdb/jaffle_shop.db`
   - **Connection mode:** Read Only (recommended for querying)
   - **Test Connection** to verify

4. **Connection Settings:**
   ```
   Database path: /Users/yury/jaffle-shop-dbt-demo/data/duckdb/jaffle_shop.db
   Read-only: ✓ (recommended to prevent lock issues)
   ```

5. **Click Finish**

### Explore Your Data

Once connected, you'll see these schemas:
- **main** - Seeds (raw_customers, raw_orders, raw_payments)
- **main_staging** - Staging tables (stg_customers, stg_orders, stg_payments)
- **main_marts** - Marts (customers, orders)
- **main_ddi** - DDI analytics (at_risk_customers, rolling_30_day_orders)
- **main_dbt_test__audit** - Test result tables

### Example Queries

```sql
-- View all customers with their lifetime value
SELECT * FROM main_marts.customers;

-- Get at-risk customers
SELECT customer_id, first_name, last_name, days_since_last_order
FROM main_ddi.at_risk_customers
ORDER BY days_since_last_order DESC;

-- Orders by status
SELECT status, COUNT(*) as count, SUM(amount) as total
FROM main_marts.orders
GROUP BY status;

-- Top 10 customers by lifetime value
SELECT customer_id, first_name, last_name, customer_lifetime_value
FROM main_marts.customers
ORDER BY customer_lifetime_value DESC
LIMIT 10;
```

---

## Option 2: Trino Connection (Not Currently Working)

**Note:** Trino with Iceberg connector is configured but not operational because dbt-duckdb creates standard DuckDB tables, not Iceberg format tables. This option is for future use when Iceberg tables are implemented.

### When Iceberg Tables Are Available in the Future:

1. **Start Trino:**
   ```bash
   podman compose up -d trino
   ```

2. **In DBeaver:**
   - New Connection → Trino/Presto
   - Host: `localhost`
   - Port: `8080`
   - Catalog: `jaffle_iceberg`
   - Schema: `marts` (or `staging`, `ddi`)
   - Username: `admin` (no password needed)

3. **Test queries:**
   ```sql
   SHOW SCHEMAS FROM jaffle_iceberg;
   SELECT * FROM jaffle_iceberg.marts.customers LIMIT 10;
   ```

---

## Troubleshooting

### "Database is locked"

**Cause:** Another process (like dbt) is using the DuckDB database.

**Solutions:**
1. Close any running dbt processes
2. Use "Read-only" mode in DBeaver connection settings
3. Or query after dbt commands complete

### "Cannot find driver"

**Solution:** DBeaver will prompt to download the DuckDB JDBC driver automatically. Click "Download/Update".

### "Cannot find database file"

**Check:** Ensure the database exists:
```bash
ls -lh ./data/duckdb/jaffle_shop.db
```

If missing, run:
```bash
./run_dbt.sh build
```

### "Connection fails with read-only"

**If you need write access:**
1. Uncheck "Read-only" in connection settings
2. Ensure no dbt processes are running
3. **Warning:** Writing to the database outside of dbt can cause inconsistencies

---

## Recommended Setup

**For Daily Use:**
- **Connection 1 (Read-Only):** For querying and analysis
  - Path: `./data/duckdb/jaffle_shop.db`
  - Read-only: ✓
  - Use this most of the time

- **Connection 2 (Read-Write):** For maintenance (rarely needed)
  - Path: `./data/duckdb/jaffle_shop.db`
  - Read-only: ✗
  - Use only when necessary (e.g., manual data fixes)

---

## Data Refresh

When you run dbt, data in DuckDB updates automatically:

```bash
# Refresh all data
./run_dbt.sh build

# Or just models
./run_dbt.sh run
```

In DBeaver: Right-click the connection → Refresh to see updated data.

---

## Alternative: Query via Command Line

If you prefer command-line queries:

```bash
# Interactive DuckDB CLI
.venv/bin/python -c "import duckdb; conn = duckdb.connect('./data/duckdb/jaffle_shop.db', read_only=True); print(conn.execute('SELECT * FROM main_marts.customers LIMIT 5').fetchdf())"

# Or use DuckDB CLI directly (if installed)
duckdb ./data/duckdb/jaffle_shop.db -readonly
```

---

## Summary

✅ **Use Option 1 (Direct DuckDB)** - This is the working solution  
❌ **Option 2 (Trino/Iceberg)** - Not yet operational (requires Iceberg table format)

For now, connect directly to DuckDB file: `/Users/yury/jaffle-shop-dbt-demo/data/duckdb/jaffle_shop.db`
