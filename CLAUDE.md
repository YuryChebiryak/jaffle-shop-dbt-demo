# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A dbt demo project built on the classic "Jaffle Shop" dataset, used to explore data contracts, data quality enforcement, and federated queries. The stack is: DuckDB + Apache Iceberg + MinIO + Trino + Apache Superset + Soda Core.

## Common Commands

Activate the virtual environment first:
```bash
source venv/bin/activate
```

| Task | Command |
|---|---|
| Full pipeline (infra + build + checks) | `./run_checks.sh` |
| Full pipeline (infra already running) | `./run_checks.sh --no-infra` |
| Verify dbt connection | `dbt debug` |
| Load seed CSVs | `dbt seed` |
| Run all models | `dbt run` |
| Run tests | `dbt test` |
| Run + test | `dbt build` |
| Run only DDI models | `dbt run -s tag:ddi --log-level debug` |
| Validate contracts | `dbt run-operation validate_contracts` |
| Register Iceberg tables | `python scripts/register_iceberg_tables.py` |
| Generate Soda checks | `python scripts/generate_soda_from_dbt_contract.py` |
| Run Soda checks | `soda scan -d jaffle_shop_datasource -c soda/configuration.yml soda/soda_checks_rolling_30_day_orders.yml` |
| Create MinIO bucket (first time) | `python scripts/setup_minio.py` |
| Serve dbt docs | `dbt docs serve` |

Start/stop infrastructure (uses `podman`, not Docker):
```bash
podman compose up -d
podman compose down
```

## Project Layout

```
jaffle-shop-dbt-demo/
├── run_checks.sh               # Full pipeline entry point
├── docker-compose.yml          # MinIO, Iceberg REST catalog, Trino, Superset
├── dbt_project.yml             # dbt project config
├── profiles.yml                # DuckDB connection profile
├── packages.yml / package-lock.yml
│
├── models/                     # dbt models
│   ├── staging/                # Views over raw seeds
│   ├── marts/                  # Business layer (Iceberg, cents amounts, BIGINT)
│   └── ddi/                    # Presentation layer (Iceberg, dollar amounts, DECIMAL(18,2))
├── seeds/                      # CSV source data
├── macros/                     # dbt macros (validate_contracts, generate_schema_name,
│                               #   materializations/external_iceberg)
│
├── scripts/                    # Python scripts and shell helpers
│   ├── register_iceberg_tables.py    # Post-build: register tables in REST catalog
│   ├── generate_soda_from_dbt_contract.py
│   ├── setup_minio.py                # First-time: create lakehouse bucket
│   ├── create_superset_dashboard.py
│   ├── dbt-mcp-interactive.py
│   ├── init_superset.sh
│   └── setup-trino-access.sh
│
├── soda/                       # Soda data quality checks
│   ├── configuration.yml       # Trino connection for Soda
│   ├── soda_checks_rolling_30_day_orders.yml
│   └── soda_checks_at_risk_customers.yml
│
├── trino/                      # Trino server config (mounted by docker-compose)
│   └── etc/
│       ├── config.properties
│       ├── jvm.config
│       └── catalog/
│           └── lakehouse.properties   # Iceberg REST catalog
│
└── docs/                       # Architecture docs and post content
    ├── step21.md
    ├── step21.txt
    ├── architecture_diagram.png
    ├── jaffle_shop_erd.png
    └── dbdiagram_definition.txt
```

## Architecture

### Stack

- **DuckDB** — dbt execution engine; writes Iceberg files to S3 via `COPY ... TO ... (FORMAT ICEBERG)`
- **Apache Iceberg** — open table format; Parquet data + metadata on MinIO
- **MinIO** — S3-compatible object storage (`s3://lakehouse/`)
- **Iceberg REST catalog** (`tabulario/iceberg-rest`, port 8181) — table registry; engines discover S3 locations here
- **Trino** (port 8080) — federated query engine; reads Iceberg via REST catalog
- **Apache Superset** (port 8088) — visualization; connects via Trino

### dbt Model Layers

- **`models/staging/`** — DuckDB views over raw seed tables. Not written to Iceberg.
- **`models/marts/`** — Business-layer Iceberg tables. Amounts stored in **cents** (BIGINT) for lossless precision.
- **`models/ddi/`** — Presentation-layer Iceberg tables tagged `serving`/`ddi`. Amounts converted to **dollars** (DECIMAL(18,2)) for consumers.

### Data Contract Enforcement

1. **dbt native contracts** (`contract: enforced: true` in `schema.yml`): column names and types validated at build time.
2. **`validate_contracts` macro** ([macros/validate_contracts.sql](macros/validate_contracts.sql)): post-build cross-check for all `serving`-tagged models. Run as a CI blocking step.
3. **Soda checks** ([scripts/generate_soda_from_dbt_contract.py](scripts/generate_soda_from_dbt_contract.py)): translates dbt tests into SodaCL and runs them via Trino against the live Iceberg tables.

### Important DuckDB + Iceberg Notes

- DuckDB cannot attach an Iceberg REST catalog directly (OAuth2 requirement in 1.4.5+). Tables are registered via `scripts/register_iceberg_tables.py` using PyIceberg after each build.
- DuckDB's `SUM` always returns `HUGEINT` regardless of input type — explicit `CAST(... AS BIGINT)` is required where contracts declare `bigint`.
- Integer division (`amount / 100`) produces `DOUBLE` in DuckDB, not `INTEGER`. Currency amounts stay in cents through all aggregations; division to dollars happens only in the DDI presentation layer.
- DuckDB writes incomplete Iceberg metadata (`last-sequence-number` missing, `sort-orders: []`). `register_iceberg_tables.py` patches both before calling the REST catalog.
- `version-hint.text` in each table's metadata folder is the authoritative pointer to the current snapshot UUID.

### Infrastructure (docker-compose)

| Service | Port | Credentials |
|---|---|---|
| MinIO | 9000 (API), 9001 (console) | minioadmin / minioadmin |
| Iceberg REST catalog | 8181 | no auth |
| Trino | 8080 | no auth |
| Apache Superset | 8088 | admin / admin |

### Packages

- `calogica/dbt_expectations` — range checks and cross-column comparisons in `models/ddi/schema.yml`.
