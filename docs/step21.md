# Step 21: Migrate from PostgreSQL to DuckDB + Apache Iceberg

## 1. System of Record and Storage Layer

After the migration, **Apache Iceberg on MinIO is the system of record and the persistence layer**. Both DuckDB and Trino become pure compute engines — they read and write Iceberg tables but hold no data themselves.

Concretely:
- **MinIO** stores the physical Parquet data files and Iceberg metadata JSON (snapshot manifests, manifest lists, table metadata) under an S3-compatible bucket, e.g. `s3://lakehouse/`.
- **An Iceberg catalog** (recommended: Project Nessie, a single-container REST catalog) tracks which path on MinIO is the current table snapshot for each table. Nessie is the right choice here because it runs as a single container, Trino has a built-in Nessie connector, and it adds git-like branching as a bonus.
- **DuckDB** is the writer: dbt drives DuckDB to transform data and write Iceberg snapshots to MinIO, registering new snapshots in Nessie.
- **Trino** is the reader: it points at the same Nessie catalog and the same MinIO bucket, so it sees exactly the same committed snapshots DuckDB wrote.
- **PostgreSQL is gone.** Superset no longer needs PostgreSQL as a data source — it keeps its own internal metadata database (which can stay as SQLite or a small Postgres instance inside the compose stack if needed, separate from the data plane).

The critical conceptual shift: previously PostgreSQL was both compute and storage. Now compute (DuckDB, Trino) and storage (Iceberg on MinIO) are separate concerns.

---

## 2. dbt Profile Changes

The current `profiles.yml` uses `type: postgres`. It needs to be replaced with a `dbt-duckdb` profile.

**Adapter change.** Replace `dbt-postgres` with `dbt-duckdb` in the Python environment. The current `requirements.txt` lists `dbt-postgres==1.9.0`; that becomes `dbt-duckdb` at the matching dbt-core version.

**Profile keys that change:**

| Current (Postgres) | New (DuckDB) | Notes |
|---|---|---|
| `type: postgres` | `type: duckdb` | Adapter switch |
| `host`, `port`, `dbname`, `user`, `password` | Removed | DuckDB has no server |
| `schema: dbt` | `schema: main` | DuckDB's default schema |
| (not present) | `path: /tmp/jaffle.duckdb` | Optional on-disk DuckDB file; for pure Iceberg output, can use `:memory:` |
| (not present) | `extensions:` block | Load `httpfs` (S3 access) and `iceberg` extensions |
| (not present) | `settings:` block | S3 endpoint (`http://minio:9000`), access key, secret key, `s3_url_style: path` |
| (not present) | `attach:` or `plugins:` block | Configure Nessie catalog registration for Iceberg output |

The `extensions` block tells dbt-duckdb to auto-install and load `httpfs` and `iceberg` at session start. The `settings` block configures the S3-compatible endpoint so that any path starting with `s3://` resolves to MinIO rather than AWS. The `s3_url_style: path` setting is critical for MinIO which does not support virtual-hosted-style URLs by default.

---

## 3. dbt Materialization Configuration for Iceberg

The `dbt-duckdb` adapter supports an **`external` materialization** that writes files to object storage rather than a local DuckDB table. This is the mechanism for writing Iceberg.

**Changes to `dbt_project.yml`:**

The staging layer currently uses `materialized: view`. dbt views are DuckDB-local and invisible to Trino. Two options:
- Keep staging as DuckDB views (invisible to Trino — acceptable since staging is intermediate).
- Convert staging to external Iceberg tables if you want Trino to be able to query raw staging data.

For marts and ddi layers, switch from `materialized: table` to `materialized: external` with per-model config specifying:
- `location`: the S3 path for this table, e.g. `s3://lakehouse/marts/customers/`
- `format: iceberg`
- Optionally `partition_by` for large tables (not needed for Jaffle Shop scale)

**Contracts.** The existing `contract: enforced: true` blocks in `schema.yml` remain valid. dbt-duckdb still enforces column names and types before writing, so the contract enforcement layer is preserved. The `data_type` values in the contracts (`integer`, `varchar`, `bigint`, `date`, `decimal(38,8)`) are DuckDB-compatible types, so no changes are needed there.

**Seeds.** Seeds are read from CSV by DuckDB. They can be written as external Iceberg tables using the same external materialization approach, or kept as DuckDB-local tables if they are only used as a source for staging models and never queried directly by Trino.

**`persist_docs`.** The current `persist_docs: true` setting writes column comments to the PostgreSQL catalog. With DuckDB + Iceberg, description persistence moves to Iceberg table metadata. This `dbt_project.yml` setting can be removed or left harmless.

**`store_failures`.** Currently stores test failures in Postgres. With DuckDB, failures are stored in the local DuckDB file (or in-memory). If you want failure tables visible in Iceberg, configure a separate store_failures schema as an external location.

---

## 4. Trino Configuration for Iceberg

The current Trino catalog file `trino/etc/catalog/jaffle_postgres.properties` (connector `postgresql`, JDBC to Postgres) is replaced with a new catalog file.

**New catalog: `lakehouse.properties`** using the Iceberg connector:

Key properties:
- `connector.name=iceberg`
- `iceberg.catalog.type=nessie` (pointing at the Nessie container, e.g. `http://nessie:19120/api/v2`)
- S3/MinIO configuration: endpoint URL, access key, secret key, path-style access enabled
- `iceberg.file-format=PARQUET` (matches what DuckDB writes)

The Nessie catalog type gives Trino direct awareness of every Iceberg snapshot that DuckDB registered. Trino queries always see the latest committed snapshot by default, but can be pointed at a historical snapshot using Iceberg time-travel syntax.

**Superset Trino connection.** Superset currently connects to Trino with catalog `jaffle_postgres`. After the migration, the Superset connection string changes the catalog name to `lakehouse`. Dataset references in Superset dashboards need to be updated from `jaffle_postgres.dbt_marts.orders` to `lakehouse.marts.orders`.

**DBeaver.** Same change: update the catalog in the connection URL.

**PostgreSQL is gone from `docker-compose.yml`.** The `postgres` service, the `depends_on: postgres` in the `superset` service, and the `jaffle_postgres` Trino catalog are all removed. MinIO, Nessie, and the Trino Iceberg catalog take their place.

---

## 5. New Data Flow: CSV Seeds to Iceberg to Trino

```
CSV files (seeds/)
      │
      ▼
dbt seed ──► DuckDB reads CSV into memory
      │
      ▼
DuckDB writes seed data as Iceberg snapshots ──► MinIO (s3://lakehouse/seeds/)
                                           └──► Nessie catalog (registers snapshot)
      │
      ▼
dbt run (staging layer)
  DuckDB reads from Iceberg seed tables on MinIO
  Executes staging SQL (stg_customers, stg_orders, stg_payments)
  Writes as Iceberg snapshots ──► MinIO (s3://lakehouse/staging/)
                             └──► Nessie (registers staging snapshots)
      │
      ▼
dbt run (marts layer)
  DuckDB reads staging Iceberg tables from MinIO
  Executes business logic SQL (customers, orders)
  dbt contract enforcement validates column types before write
  Writes as Iceberg snapshots ──► MinIO (s3://lakehouse/marts/)
                             └──► Nessie (registers marts snapshots)
      │
      ▼
dbt run (ddi layer)
  DuckDB reads marts Iceberg tables from MinIO
  Executes analytics SQL (rolling_30_day_orders, at_risk_customers)
  Writes as Iceberg snapshots ──► MinIO (s3://lakehouse/ddi/)
                             └──► Nessie (registers ddi snapshots)
      │
      ▼
Trino (Iceberg connector → Nessie catalog → MinIO)
  Queries lakehouse.marts.orders, lakehouse.ddi.rolling_30_day_orders, etc.
      │
      ├──► DBeaver (JDBC to Trino :8080)
      └──► Apache Superset (SQLAlchemy Trino connection)
```

**Key properties of this flow:**

- DuckDB and Trino never connect to each other. Their only shared state is MinIO (data files) and Nessie (snapshot metadata).
- Each `dbt run` creates a new Iceberg snapshot. The previous snapshot remains intact and addressable until explicitly expired.
- `dbt test` runs read from the Iceberg tables via DuckDB, so tests validate the committed state.
- `dbt build` (run + test + seed) is the canonical full-pipeline command and works unchanged.

---

## 6. Sample Tests for Iceberg Versioning and Rollback

This scenario exercises Iceberg's snapshot isolation and the `rollback_to_snapshot` procedure.

**Step 1 — Baseline: clean load**

Run `dbt build`. All dbt tests pass: `unique`, `not_null`, `accepted_values` on `status`, `expect_column_values_to_be_between` on amounts and order counts. Record the snapshot ID from Nessie (or from Trino's `"$snapshots"` metadata table for each Iceberg table).

**Step 2 — Inject faulty data**

Simulate a bad ingestion by modifying a seed CSV or running `dbt run` with a modified model that introduces:
- Duplicate `order_id` values (violates `unique` test on `orders`)
- A `status` value of `pending` which is not in the accepted values list
- A `rolling_30_day_amount` that exceeds the `max_value: 30000000` bound in `schema.yml`
- Null values in `customer_id` on `orders` (violates `not_null`)

**Step 3 — Detect with dbt tests**

Run `dbt test`. Expected failures:
- `orders.unique.order_id` — detects the duplicate keys
- `orders.accepted_values.status` — detects the invalid status `pending`
- `rolling_30_day_orders.expect_column_values_to_be_between.rolling_30_day_amount` — detects the out-of-range aggregate
- `orders.not_null.customer_id` — detects the null foreign key

Because `store_failures: true` is set, the failing row sets are stored in Iceberg tables under the dbt test failures schema, giving a permanent, queryable record of which rows failed and at which snapshot.

**Step 4 — Rollback via Iceberg**

Using Trino, query `lakehouse.marts."orders$snapshots"` to list all snapshots with their committed timestamps and snapshot IDs. Identify the snapshot ID of the last known-good state from Step 1.

Execute `ALTER TABLE lakehouse.marts.orders EXECUTE rollback_to_snapshot(<snapshot_id>)`. Repeat for every affected table (`orders`, `rolling_30_day_orders`, etc.).

After rollback, Nessie points to the previous snapshot. The faulty Parquet files remain in MinIO but are no longer referenced by the current table metadata. They will be removed by the next expiry sweep.

**Step 5 — Verify rollback with dbt tests**

Run `dbt test` again. Because Trino and DuckDB both read through the same Nessie catalog, DuckDB now sees the rolled-back snapshot. All tests pass, confirming the table contents are identical to Step 1.

**Step 6 — Time-travel verification test**

Write a dbt singular test that uses Iceberg time-travel syntax to compare row counts or checksums across snapshots: query the current snapshot and the snapshot immediately before it, assert the row counts match and the aggregates are within bounds. This test can run after every `dbt build` as an automated sanity check that no run silently introduced large deviations.

---

## Infrastructure Summary (New `docker-compose.yml` Services)

| Service | Port | Role | Replaces |
|---|---|---|---|
| MinIO | 9000/9001 | Object storage (Parquet + Iceberg metadata) | postgres data volume |
| Nessie | 19120 | Iceberg REST catalog | postgres system catalog |
| Trino | 8080 | Query engine (Iceberg connector) | Trino (postgres connector) |
| Superset | 8088 | BI tool (unchanged) | Superset (unchanged) |

PostgreSQL is removed entirely. DuckDB runs locally (not containerized) as the dbt execution engine. The `dbt-duckdb` adapter is installed in the `venv` via `uv pip install dbt-duckdb`, replacing `dbt-postgres`.
