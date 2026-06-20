#!/usr/bin/env bash
# Full pipeline: start infrastructure, build dbt, validate contracts, register
# Iceberg tables, generate and run Soda checks.
#
# Usage:
#   ./run_checks.sh            # normal run
#   ./run_checks.sh --no-infra # skip podman start (infra already running)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

source venv/bin/activate

NO_INFRA=false
for arg in "$@"; do
  [[ "$arg" == "--no-infra" ]] && NO_INFRA=true
done

# ── 1. Infrastructure ────────────────────────────────────────────────────────
if [[ "$NO_INFRA" == false ]]; then
  echo "==> Starting Podman machine"
  podman machine start 2>/dev/null || echo "    (already running)"

  echo "==> Starting services (MinIO, Iceberg REST catalog, Trino, Superset)"
  podman compose up -d

  echo "==> Waiting for Trino to be ready..."
  until curl -sf http://localhost:8080/v1/info | grep -q '"starting":false'; do
    sleep 3
  done
  echo "    Trino ready."
fi

# ── 2. dbt build ────────────────────────────────────────────────────────────
echo ""
echo "==> dbt build (seed + run + test)"
dbt build

# ── 3. Register Iceberg tables in REST catalog ───────────────────────────────
echo ""
echo "==> Registering Iceberg tables"
python scripts/register_iceberg_tables.py

# ── 4. dbt contract validation ───────────────────────────────────────────────
echo ""
echo "==> Validating dbt contracts (serving-tagged models)"
dbt run-operation validate_contracts

# ── 5. Soda checks ───────────────────────────────────────────────────────────
echo ""
echo "==> Generating Soda checks from dbt contracts"
python scripts/generate_soda_from_dbt_contract.py

echo ""
echo "==> Running Soda checks: rolling_30_day_orders"
soda scan -d jaffle_shop_datasource -c soda/configuration.yml \
  soda/soda_checks_rolling_30_day_orders.yml

echo ""
echo "==> Running Soda checks: at_risk_customers"
soda scan -d jaffle_shop_datasource -c soda/configuration.yml \
  soda/soda_checks_at_risk_customers.yml


# ── 6. Superset setup (idempotent) ───────────────────────────────────────────
echo ""
echo "==> Setting up Superset (Trino database, datasets, dashboard)"
python scripts/setup_superset.py

# ── 7. Superset integration tests ────────────────────────────────────────────
echo ""
echo "==> Running Superset integration tests"
python scripts/test_superset.py

echo ""
echo "All checks passed."
