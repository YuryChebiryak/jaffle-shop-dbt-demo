#!/bin/bash

# Wait for Trino to be ready
echo "Waiting for Trino to be ready..."
sleep 10

echo "Testing Data Analyst Access (Should succeed for rolling_30_day_orders, fail for at_risk_customers)"
echo "------------------------------------------------------------------------------------------------"
echo "Querying rolling_30_day_orders as data_analyst:"
podman exec -it trino trino --server localhost:8080 --user data_analyst --execute "SELECT count(*) FROM jaffle_postgres.dbt_ddi.rolling_30_day_orders" || echo "Failed as expected"

echo "Querying at_risk_customers as data_analyst:"
podman exec -it trino trino --server localhost:8080 --user data_analyst --execute "SELECT count(*) FROM jaffle_postgres.dbt_ddi.at_risk_customers" || echo "Failed as expected"

echo ""
echo "Testing Data Scientist Access (Should fail for rolling_30_day_orders, succeed for at_risk_customers)"
echo "--------------------------------------------------------------------------------------------------"
echo "Querying rolling_30_day_orders as data_scientist:"
podman exec -it trino trino --server localhost:8080 --user data_scientist --execute "SELECT count(*) FROM jaffle_postgres.dbt_ddi.rolling_30_day_orders" || echo "Failed as expected"

echo "Querying at_risk_customers as data_scientist:"
podman exec -it trino trino --server localhost:8080 --user data_scientist --execute "SELECT count(*) FROM jaffle_postgres.dbt_ddi.at_risk_customers" || echo "Failed as expected"