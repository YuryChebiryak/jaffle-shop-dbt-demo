This repository explores how data contracts can be defined and enforced for the classic Jaffle Shop dbt demo.

This is a post series titled "Data Contracts with dbt":

[1/7: Why Data Contracts Matter](https://www.linkedin.com/feed/update/urn:li:activity:7367654714525642753/)
[2/7 Declaring Data Contracts in dbt](https://www.linkedin.com/feed/update/urn:li:activity:7369170884021964801/)
[3/7 Enforcing with Data Tests](https://www.linkedin.com/feed/update/urn:li:activity:7369463558130098178/)
[4/7 Documentation Matters](https://www.linkedin.com/feed/update/urn:li:activity:7370036803829063680/?updateEntityUrn=urn%3Ali%3Afs_feedUpdate%3A%28V2%2Curn%3Ali%3Aactivity%3A7370036803829063680%29)
[5/7 Tracking Data Consumers with dbt Exposures](https://www.linkedin.com/feed/update/urn:li:activity:7370761583909568512/?updateEntityUrn=urn%3Ali%3Afs_feedUpdate%3A%28V2%2Curn%3Ali%3Aactivity%3A7370761583909568512%29)
[6/7 Data Contracts, ELT, and the role of DBT](https://www.linkedin.com/feed/update/urn:li:activity:7371108866610126848/?updateEntityUrn=urn%3Ali%3Afs_feedUpdate%3A%28V2%2Curn%3Ali%3Aactivity%3A7371108866610126848%29)
[7/7 Digging into Failures with store_failures](https://www.linkedin.com/feed/update/urn:li:activity:7371856485129011201/?updateEntityUrn=urn%3Ali%3Afs_feedUpdate%3A%28V2%2Curn%3Ali%3Aactivity%3A7371856485129011201%29)
[8/7 Testing Data Contracts with datacontract.com CLI](https://www.linkedin.com/feed/update/urn:li:activity:7375296445676945408/?updateEntityUrn=urn%3Ali%3Afs_feedUpdate%3A%28V2%2Curn%3Ali%3Aactivity%3A7375296445676945408%29)
[9/7 Federated Access with Trino](https://www.linkedin.com/posts/yurychebiryak_datamesh-dbt-vibecoding-activity-7377590326426775552-ELRJ?utm_source=share&utm_medium=member_ios&rcm=ACoAAAEI_0oB7fYEPncLP2s2k_qPhBZeQS5RO7s)
[10/7 Testing Data Expectations in dbt](https://www.linkedin.com/feed/update/urn:li:activity:7380127053439819776/)
[11/7 Atomicity and Idempotence in Data Pipelines](https://www.linkedin.com/posts/yurychebiryak_𝟏𝟏𝟕-atomicity-and-idempotence-in-data-activity-7382663779572076544-uRdg?utm_source=share&utm_medium=member_ios&rcm=ACoAAAEI_0oB7fYEPncLP2s2k_qPhBZeQS5RO7s)
[12/7 Why MCP Matters](https://www.linkedin.com/feed/update/urn:li:activity:7385200486360027136/)
[13/7 What is dbt MCP](https://www.linkedin.com/feed/update/urn:li:activity:7387737211452067840/)
[14/7 How to use dbt MCP in practice](https://www.linkedin.com/feed/update/urn:li:activity:7390289021819670528/)
[Post 15 – Experimenting Safely with dbt clone and dbt defer](https://www.linkedin.com/feed/update/urn:li:activity:7392912843991330816/)
[Post 16: Context Drift in Data-Driven Applications](https://www.linkedin.com/feed/update/urn:li:activity:7415468249125068801/)
[Post 17 – Investigating Attribute Lineage with an LLM and dbt MCP](https://www.linkedin.com/feed/update/urn:li:activity:7398081603836579840/)
[Post 18 – Validating dbt Models Against the Data Contract (without abusing data tests)](https://www.linkedin.com/feed/update/urn:li:activity:7400877372180152320/)
[Post 19 Automating Data Quality Checks from dbt Contracts Using Soda](https://www.linkedin.com/feed/update/urn:li:activity:7405384020068376577/)
[Post 20: Works in Staging, Breaks in Prod](https://www.linkedin.com/feed/update/urn:li:activity:7418222409335377920/)
[Post 21: dbt + DuckDB + Apache Iceberg — an Open Lakehouse](https://www.linkedin.com/feed/update/urn:li:activity:7418222409335377920/)

(C) 2025 Chebiryak Consulting https://consulting.chebiryak.name/about-me/

---

## Architecture

This project has evolved from a PostgreSQL-backed dbt setup to an **open lakehouse** architecture built on DuckDB + Apache Iceberg + MinIO.

### Stack

| Component | Role |
|---|---|
| **DuckDB** | dbt execution engine; writes Iceberg files directly to S3 |
| **Apache Iceberg** | Open table format; stores Parquet data + metadata on MinIO |
| **MinIO** | S3-compatible object storage (`s3://lakehouse/`) |
| **Iceberg REST catalog** (`tabulario/iceberg-rest`) | Metadata catalog; engines discover table locations here |
| **Trino** | Federated query engine; reads Iceberg tables via REST catalog |
| **Apache Superset** | Visualization layer; connects via Trino |

### Data Flow

```
dbt build
  └─ DuckDB executes SQL models
       └─ COPY ... TO 's3://lakehouse/<model>.iceberg/' (FORMAT ICEBERG)
            └─ MinIO stores Parquet data + Iceberg metadata files

python register_iceberg_tables.py
  └─ Scans MinIO for latest metadata.json per table
  └─ Patches DuckDB metadata omissions (last-sequence-number, sort-orders)
  └─ Registers each table in the Iceberg REST catalog

Trino (catalog: lakehouse)
  └─ Queries REST catalog for table location
  └─ Reads Parquet files from MinIO
```

### dbt Model Layers

| Layer | Path | Materialization | Schema |
|---|---|---|---|
| Staging | `models/staging/` | view | `staging` |
| Marts | `models/marts/` | external (Iceberg) | `marts` |
| DDI | `models/ddi/` | external (Iceberg) | `ddi` |

Marts and DDI models are written as Iceberg tables at `s3://lakehouse/<model>.iceberg/`. The path is derived automatically from `external_root: s3://lakehouse` in `profiles.yml` — no per-model S3 location is hardcoded.

### Data Contract Enforcement

All marts and DDI models carry `contract: enforced: true` in their `schema.yml`. dbt validates column names and types at build time. Two additional layers run on top:

1. **`validate_contracts` macro** — post-build cross-check comparing live schema against the contract spec for models tagged `serving`. Catches missing columns, extra columns, and type mismatches.
2. **Soda checks** — generated from dbt tests via `generate_soda_from_dbt_contract.py`; runs as an independent quality gate.

### Why DuckDB writes Iceberg directly (no catalog attach)

DuckDB 1.4.5+ requires OAuth2 when attaching an Iceberg REST catalog (`ATTACH ... (TYPE ICEBERG)`). There is no bypass. Instead this project uses DuckDB's `COPY ... TO ... (FORMAT ICEBERG)` to write Iceberg files directly to MinIO, then `register_iceberg_tables.py` registers the written metadata in the REST catalog. The REST catalog becomes the single source of truth for table locations — Trino and any other engine that connects to it receives the S3 path from the catalog, not from config.

### Infrastructure Services

| Service | Port | Credentials |
|---|---|---|
| MinIO (S3) | 9000 (API), 9001 (console) | minioadmin / minioadmin |
| Iceberg REST catalog | 8181 | no auth |
| Trino | 8080 | no auth |
| Apache Superset | 8088 | admin / admin |

---

## Prerequisites

1. git
2. Python 3.9 or higher
3. Podman (used instead of Docker)

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/YuryChebiryak/jaffle-shop-dbt-demo.git
cd jaffle-shop-dbt-demo
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install --upgrade pip
pip install uv
uv pip install -r requirements.txt
```

### 3. Install dbt packages

```bash
dbt deps
```

### 4. Install and start Podman

```bash
brew install podman
podman machine init
podman machine start
```

### 5. Start infrastructure

```bash
podman compose up -d
```

This starts MinIO, the Iceberg REST catalog, Trino, and Superset.

### 6. Create the MinIO bucket (first time only)

```bash
python setup_minio.py
```

---

## Running the pipeline

### Build all dbt models and run tests

```bash
dbt build
```

Expected: `PASS=59 WARN=0 ERROR=0`

### Register Iceberg tables in the REST catalog

Run this after every `dbt build`:

```bash
python register_iceberg_tables.py
```

This script:
1. Scans MinIO for the latest `*.metadata.json` for each model
2. Patches DuckDB metadata omissions (`last-sequence-number`, `sort-orders`) required by the REST catalog
3. Calls the Iceberg REST catalog's `registerTable` endpoint via PyIceberg

### Verify with Trino

```bash
trino --server localhost:8080 --catalog lakehouse
```

```sql
SELECT customer_id, first_name, customer_lifetime_value FROM marts.customers LIMIT 5;
SELECT order_date, rolling_30_day_amount FROM ddi.rolling_30_day_orders LIMIT 5;
SELECT customer_id, days_since_last_order FROM ddi.at_risk_customers LIMIT 5;
```

---

## Selective model execution

```bash
# Run only DDI models
dbt run -s tag:ddi --log-level debug

# Run only marts
dbt run -s marts.*
```

---

## Data quality and contract validation

### dbt native contract enforcement

All marts and DDI models declare `contract: enforced: true`. dbt validates column names and types at build time — mismatches fail the build before any data is written.

### Cross-schema contract validation macro

```bash
dbt run-operation validate_contracts
```

Checks models tagged `serving` for missing columns, extra columns, and type mismatches against the contract spec. Use as a CI blocking step or pre-commit hook.

### Soda checks

Generate SodaCL checks from dbt contract definitions:

```bash
python3 generate_soda_from_dbt_contract.py
```

Run the generated checks:

```bash
soda scan -d jaffle_shop_datasource -c .soda/configuration.yml soda_checks_rolling_30_day_orders.yml
```

---

## Trino

Trino is available at [http://localhost:8080](http://localhost:8080) and exposes the Iceberg catalog as `lakehouse`.

### Connecting with DBeaver

1. Create a new connection, select **Trino**
2. Host: `localhost`, Port: `8080`, Catalog: `lakehouse`
3. No username/password required
4. Query tables as `lakehouse.marts.customers`, `lakehouse.ddi.rolling_30_day_orders`, etc.

---

## Apache Superset

Superset is available at [http://localhost:8088](http://localhost:8088) (admin / admin).

Connect Superset to the data by adding a **Trino** database connection:

- **SQLAlchemy URI**: `trino://trino_user@trino:8080/lakehouse`

Then create datasets from `marts.customers`, `marts.orders`, `ddi.rolling_30_day_orders`, and `ddi.at_risk_customers`.

---

## DDI models

### `rolling_30_day_orders`

Time-series analysis of completed orders:

| Column | Type | Description |
|---|---|---|
| `order_date` | DATE | Order date |
| `total_amount` | DECIMAL(38,8) | Daily total payment amount |
| `order_count` | DECIMAL(38,8) | Daily completed order count |
| `rolling_30_day_amount` | DECIMAL(38,8) | 30-day rolling sum of amounts |
| `rolling_30_day_orders` | DECIMAL(38,8) | 30-day rolling order count |
| `rolling_30_day_avg_daily` | DECIMAL(38,8) | 30-day rolling average daily amount |

### `at_risk_customers`

Customers with no orders in the last 60 days (based on the most recent order date in the dataset):

| Column | Type | Description |
|---|---|---|
| `customer_id` | INTEGER | Customer identifier |
| `first_name` | VARCHAR | First name |
| `last_name` | VARCHAR | Last name |
| `first_order_date` | DATE | Date of first order |
| `last_order_date` | DATE | Date of most recent order |
| `total_orders` | BIGINT | Total number of orders |
| `completed_orders` | BIGINT | Number of completed orders |
| `reference_date` | DATE | Dataset's most recent order date (used as "today") |
| `days_since_last_order` | INTEGER | Days between last order and reference date |

---

## Known DuckDB + Iceberg integration notes

- **Integer division**: `amount / 100` in DuckDB produces `DOUBLE`, not `INTEGER`. Downstream aggregations must be explicitly cast to match the contract type (`CAST(SUM(amount) AS BIGINT)`).
- **Iceberg metadata patches**: DuckDB omits `last-sequence-number` from Iceberg v2 metadata and writes `sort-orders: []`. Both are invalid per the Iceberg spec and cause the REST catalog's `registerTable` to reject them. `register_iceberg_tables.py` patches both fields before registration.
- **S3 paths**: dbt-duckdb writes external Iceberg tables to `<external_root>/<model_name>.iceberg/`. The schema segment is not included in the path by default.
