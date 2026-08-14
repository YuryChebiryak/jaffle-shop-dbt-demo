#!/usr/bin/env python3
"""
Trino + Iceberg integration tests.

Checks:
  1. Iceberg REST catalog — all 4 tables are registered
  2. MinIO — Parquet data files exist for each table
  3. Trino row counts match the seed data (catches stale/wrong snapshot)
  4. Business invariants via Trino:
       - at_risk_customers: every row has days_since_last_order >= 60
       - rolling_30_day_orders: rolling_30_day_amount >= total_amount on every row
       - marts.customers: customer_lifetime_value >= 0
       - marts.orders: amount == sum of payment-method columns on every row

Exit 0 on success, exit 1 on any failure.
"""

import sys

import boto3
import trino
from pyiceberg.catalog.rest import RestCatalog

TRINO_HOST = "localhost"
TRINO_PORT = 8080
REST_CATALOG_URI = "http://localhost:8181"
MINIO_ENDPOINT = "http://localhost:9000"
MINIO_KEY = "minioadmin"
MINIO_SECRET = "minioadmin"
BUCKET = "lakehouse"

# Expected row counts driven by seed CSVs (raw_customers=100, raw_orders=99)
EXPECTED_COUNTS = {
    ("marts", "customers"): 100,
    ("marts", "orders"): 99,
}

PASS = "PASS"
FAIL = "FAIL"
failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"  [{PASS}] {label}")
    else:
        print(f"  [{FAIL}] {label}" + (f": {detail}" if detail else ""))
        failures.append(label)


def trino_query(sql):
    conn = trino.dbapi.connect(
        host=TRINO_HOST, port=TRINO_PORT,
        user="trino_user", http_scheme="http",
    )
    cur = conn.cursor()
    cur.execute(sql)
    return cur.fetchall()


def count(schema, table):
    rows = trino_query(f"SELECT count(*) FROM lakehouse.{schema}.{table}")
    return rows[0][0]


def violation_count(sql):
    """Return number of rows that violate an invariant (expect 0)."""
    rows = trino_query(sql)
    return rows[0][0]


# ── 1. Iceberg REST catalog ──────────────────────────────────────────────────
print("-- Iceberg REST catalog")
catalog = RestCatalog("rest", uri=REST_CATALOG_URI)

expected_tables = [
    ("marts", "customers"),
    ("marts", "orders"),
    ("ddi", "rolling_30_day_orders"),
    ("ddi", "at_risk_customers"),
]
for schema, table in expected_tables:
    try:
        registered = [(ns, t) for ns, t in catalog.list_tables(schema)]
        found = (schema, table) in registered or any(t == table for _, t in registered)
        check(f"Iceberg catalog: {schema}.{table} registered", found)
    except Exception as e:
        check(f"Iceberg catalog: {schema}.{table} registered", False, str(e))

# ── 2. MinIO Parquet files ───────────────────────────────────────────────────
print("\n-- MinIO Parquet data files")
s3 = boto3.client(
    "s3", endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_KEY, aws_secret_access_key=MINIO_SECRET,
)
iceberg_prefixes = {
    "customers": "customers.iceberg/",
    "orders": "orders.iceberg/",
    "rolling_30_day_orders": "rolling_30_day_orders.iceberg/",
    "at_risk_customers": "at_risk_customers.iceberg/",
}
for tbl, prefix in iceberg_prefixes.items():
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix + "data/")
    parquet_files = [o for o in resp.get("Contents", []) if o["Key"].endswith(".parquet")]
    check(f"MinIO: {tbl} has Parquet data files", len(parquet_files) > 0,
          f"found {len(parquet_files)} files under s3://{BUCKET}/{prefix}data/")

# ── 3. Trino row counts ──────────────────────────────────────────────────────
print("\n-- Trino row counts")
for (schema, table), expected in EXPECTED_COUNTS.items():
    try:
        n = count(schema, table)
        check(
            f"lakehouse.{schema}.{table}: {n} rows == {expected} (seed count)",
            n == expected,
            f"got {n}, expected {expected} — possible stale Iceberg snapshot",
        )
    except Exception as e:
        check(f"lakehouse.{schema}.{table} row count", False, str(e))

for schema, table in [("ddi", "rolling_30_day_orders"), ("ddi", "at_risk_customers")]:
    try:
        n = count(schema, table)
        check(f"lakehouse.{schema}.{table}: has rows", n > 0, f"got {n}")
    except Exception as e:
        check(f"lakehouse.{schema}.{table} has rows", False, str(e))

# ── 4. Business invariants ───────────────────────────────────────────────────
print("\n-- Business invariants")

try:
    bad = violation_count(
        "SELECT count(*) FROM lakehouse.ddi.at_risk_customers "
        "WHERE days_since_last_order < 60"
    )
    check("at_risk_customers: all rows have days_since_last_order >= 60", bad == 0,
          f"{bad} rows violate the >= 60 threshold")
except Exception as e:
    check("at_risk_customers: days_since_last_order >= 60", False, str(e))

try:
    bad = violation_count(
        "SELECT count(*) FROM lakehouse.ddi.rolling_30_day_orders "
        "WHERE rolling_30_day_amount < total_amount"
    )
    check("rolling_30_day_orders: rolling_30_day_amount >= total_amount on every row", bad == 0,
          f"{bad} rows violate the rolling >= daily invariant")
except Exception as e:
    check("rolling_30_day_orders: rolling amount >= daily", False, str(e))

try:
    bad = violation_count(
        "SELECT count(*) FROM lakehouse.marts.customers "
        "WHERE customer_lifetime_value < 0"
    )
    check("marts.customers: customer_lifetime_value >= 0 (amounts in cents)", bad == 0,
          f"{bad} rows have negative lifetime value")
except Exception as e:
    check("marts.customers: lifetime_value >= 0", False, str(e))

try:
    bad = violation_count(
        "SELECT count(*) FROM lakehouse.marts.orders "
        "WHERE amount != credit_card_amount + coupon_amount + bank_transfer_amount + gift_card_amount"
    )
    check("marts.orders: amount == sum of payment-method columns", bad == 0,
          f"{bad} rows have amount mismatch")
except Exception as e:
    check("marts.orders: amount == payment method sum", False, str(e))

# ── Summary ──────────────────────────────────────────────────────────────────
print()
if failures:
    print(f"FAILED ({len(failures)} check(s)):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("All checks passed.")
