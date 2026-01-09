import duckdb

conn = duckdb.connect('./data/duckdb/jaffle_shop.db', read_only=True)

print("=" * 60)
print("DuckDB Database Verification")
print("=" * 60)

# List all tables
print("\nAll Tables:")
result = conn.execute("""
    SELECT table_schema, table_name
    FROM information_schema.tables
    WHERE table_schema NOT LIKE 'information_%'
      AND table_schema NOT LIKE 'pg_%'
    ORDER BY table_schema, table_name
""").fetchall()

for schema, table in result:
    print(f"  {schema}.{table}")

# Count rows in each layer
print("\n" + "=" * 60)
print("Row Counts by Layer")
print("=" * 60)

print("\nSeeds (main schema):")
for table in ['raw_customers', 'raw_orders', 'raw_payments']:
    count = conn.execute(f'SELECT COUNT(*) FROM main.{table}').fetchone()[0]
    print(f"  {table}: {count} rows")

print("\nStaging (main_staging schema):")
for table in ['stg_customers', 'stg_orders', 'stg_payments']:
    count = conn.execute(f'SELECT COUNT(*) FROM main_staging.{table}').fetchone()[0]
    print(f"  {table}: {count} rows")

print("\nMarts (main_marts schema):")
for table in ['customers', 'orders']:
    count = conn.execute(f'SELECT COUNT(*) FROM main_marts.{table}').fetchone()[0]
    print(f"  {table}: {count} rows")

print("\nDDI (main_ddi schema):")
for table in ['at_risk_customers', 'rolling_30_day_orders']:
    count = conn.execute(f'SELECT COUNT(*) FROM main_ddi.{table}').fetchone()[0]
    print(f"  {table}: {count} rows")

# Sample data from marts
print("\n" + "=" * 60)
print("Sample Data - Customers (first 3 rows)")
print("=" * 60)
customers = conn.execute('SELECT * FROM main_marts.customers LIMIT 3').fetchall()
for row in customers:
    print(f"  Customer {row[0]}: {row[1]} {row[2]}, Orders: {row[5]}, LTV: ${row[6]}")

print("\n" + "=" * 60)
print("Sample Data - At Risk Customers")
print("=" * 60)
at_risk = conn.execute('SELECT customer_id, first_name, last_name, days_since_last_order FROM main_ddi.at_risk_customers LIMIT 3').fetchall()
for row in at_risk:
    print(f"  Customer {row[0]}: {row[1]} {row[2]}, {row[3]} days since last order")

print("\n" + "=" * 60)
print("✅ All tables verified successfully!")
print("=" * 60)

conn.close()
