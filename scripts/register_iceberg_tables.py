"""
Register dbt-written Iceberg tables in the REST catalog so Trino can query them.

Run after every `dbt build`:
    python register_iceberg_tables.py

How it works:
  1. Scans MinIO for Iceberg metadata files written by DuckDB.
  2. Patches missing `last-sequence-number` (DuckDB omits it; REST catalog requires it).
  3. Calls the Iceberg REST catalog's `registerTable` endpoint (PyIceberg).

The S3 warehouse path convention (set by `external_root` in profiles.yml):
  s3://lakehouse/<schema>/<model_name>/
"""

import json
import re
import boto3
from botocore.client import Config
from pyiceberg.catalog.rest import RestCatalog

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
BUCKET = "lakehouse"

REST_CATALOG_URI = "http://localhost:8181"

# (iceberg_namespace, model_name, s3_prefix)
# dbt-duckdb external materialization writes to <external_root>/<model>.iceberg/
TABLES = [
    ("marts", "customers",             "customers.iceberg/"),
    ("marts", "orders",                "orders.iceberg/"),
    ("ddi",   "rolling_30_day_orders", "rolling_30_day_orders.iceberg/"),
    ("ddi",   "at_risk_customers",     "at_risk_customers.iceberg/"),
]


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def latest_metadata_key(s3, prefix):
    # version-hint.text is the authoritative pointer to the current metadata file.
    # DuckDB writes UUID-named metadata files and sets this hint after each build.
    try:
        hint = s3.get_object(Bucket=BUCKET, Key=prefix + "metadata/version-hint.text")
        uuid = hint["Body"].read().decode().strip()
        return f"{prefix}metadata/{uuid}.metadata.json"
    except s3.exceptions.NoSuchKey:
        pass

    # Fallback: find the newest metadata.json by LastModified timestamp.
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix + "metadata/")
    candidates = [
        o for o in resp.get("Contents", [])
        if o["Key"].endswith(".metadata.json")
    ]
    if not candidates:
        raise FileNotFoundError(f"No metadata found under s3://{BUCKET}/{prefix}")
    return max(candidates, key=lambda o: o["LastModified"])["Key"]


def patch_and_upload(s3, key):
    """Fix DuckDB Iceberg metadata omissions before REST catalog registration.

    DuckDB omits `last-sequence-number` and writes `sort-orders: []` (empty),
    both of which are rejected by the Iceberg REST catalog.
    """
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    meta = json.loads(obj["Body"].read())
    changed = False

    if "last-sequence-number" not in meta:
        sequences = [
            snap.get("sequence-number", 0)
            for snap in meta.get("snapshots", [])
        ]
        meta["last-sequence-number"] = max(sequences, default=0)
        print(f"    patched last-sequence-number → {meta['last-sequence-number']}")
        changed = True

    if not meta.get("sort-orders"):
        meta["sort-orders"] = [{"order-id": 0, "fields": []}]
        print("    patched sort-orders → [{order-id: 0, fields: []}]")
        changed = True

    if changed:
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=json.dumps(meta).encode(),
            ContentType="application/json",
        )
    return f"s3://{BUCKET}/{key}"


def ensure_namespace(catalog, namespace):
    try:
        catalog.create_namespace(namespace)
        print(f"  created namespace '{namespace}'")
    except Exception:
        pass  # already exists


def main():
    s3 = s3_client()
    catalog = RestCatalog(
        "lakehouse",
        **{
            "uri": REST_CATALOG_URI,
            "s3.endpoint": MINIO_ENDPOINT,
            "s3.access-key-id": MINIO_ACCESS_KEY,
            "s3.secret-access-key": MINIO_SECRET_KEY,
            "s3.path-style-access": "true",
            "s3.region": "us-east-1",
        },
    )

    for namespace, table, prefix in TABLES:
        print(f"\n{namespace}.{table}")
        try:
            key = latest_metadata_key(s3, prefix)
            metadata_location = patch_and_upload(s3, key)
            print(f"  metadata → {metadata_location}")

            ensure_namespace(catalog, namespace)

            # Drop if already registered (idempotent re-run after dbt rebuild).
            try:
                catalog.drop_table((namespace, table))
                print("  dropped stale registration")
            except Exception:
                pass

            catalog.register_table((namespace, table), metadata_location)
            print("  registered OK")

        except FileNotFoundError as e:
            print(f"  SKIP (not yet written): {e}")
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\nDone — Trino can now query via catalog 'lakehouse'.")


if __name__ == "__main__":
    main()
