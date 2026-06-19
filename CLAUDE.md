# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A dbt demo project built on the classic "Jaffle Shop" dataset, used to explore data contracts, data quality enforcement, and federated queries. The stack is: PostgreSQL + dbt + Apache Superset + Trino + Soda Core.

## Common Commands

Activate the virtual environment first:
```bash
source venv/bin/activate
```

| Task | Command |
|---|---|
| Verify connection | `dbt debug` |
| Load seed CSVs | `dbt seed` |
| Run all models | `dbt run` |
| Run tests | `dbt test` |
| Run + test + docs | `dbt build` |
| Run only DDI models | `dbt run -s tag:ddi --log-level debug` |
| Validate contracts | `dbt run-operation validate_contracts` |
| Generate Soda checks | `python3 generate_soda_from_dbt_contract.py` |
| Run Soda checks | `soda scan -d jaffle_shop_datasource -c .soda/configuration.yml soda_checks_rolling_30_day_orders.yml` |
| Serve docs | `dbt docs serve` |

Start/stop infrastructure (uses `podman`, not Docker):
```bash
podman compose up -d
podman compose down
```

## Architecture

### dbt Model Layers

- **`models/staging/`** — Views over raw seed tables (`stg_customers`, `stg_orders`, `stg_payments`). Schema: `jaffle-shop-classic`.
- **`models/marts/`** — Business-layer tables (`customers`, `orders`) with enforced dbt data contracts. Schema: `jaffle-shop-classic`.
- **`models/ddi/`** — Analytics models (`rolling_30_day_orders`, `at_risk_customers`) with enforced contracts and tagged `serving`/`ddi`. Schema: `ddi`.

All models persist docs to the database (`persist_docs: true` in `dbt_project.yml`). Test failures are stored (`store_failures: true`).

### Data Contract Enforcement — Two Layers

1. **dbt native contracts** (`contract: enforced: true` in `schema.yml`): dbt enforces column names and types at model build time for models in `models/marts/` and `models/ddi/`.

2. **Custom `validate_contracts` macro** ([macros/validate_contracts.sql](macros/validate_contracts.sql)): Post-build cross-check that compares the live database schema against the contract spec for all models tagged `serving`. Catches missing columns, extra columns, and type mismatches. Run as a CI blocking step or pre-commit hook.

3. **Soda checks** ([generate_soda_from_dbt_contract.py](generate_soda_from_dbt_contract.py)): Script that translates dbt tests (`not_null`, `unique`, `accepted_values`, `dbt_expectations`) from `schema.yml` into SodaCL YAML files. Keeps Soda checks in sync with dbt contract definitions.

### Infrastructure (docker-compose)

| Service | Port | Credentials |
|---|---|---|
| PostgreSQL | 5432 | dbt/dbt, db: dbt |
| Apache Superset | 8088 | admin/admin |
| Trino | 8080 | no auth |

Trino registers Postgres as catalog `jaffle_postgres`. The `trino_user` has read-only access to `dbt_ddi` and `dbt_marts` schemas only.

### Schema Naming

dbt prefixes the schema name from `profiles.yml` with the sub-schema from `dbt_project.yml`:
- Staging/Marts models → `dbt.jaffle-shop-classic.<table>`
- DDI models → `dbt.ddi.<table>` (exposed in Superset as `dbt_ddi.<table>`)

### Packages

- `calogica/dbt_expectations` — used for range checks (`expect_column_values_to_be_between`) and cross-column comparisons in `models/ddi/schema.yml`.
