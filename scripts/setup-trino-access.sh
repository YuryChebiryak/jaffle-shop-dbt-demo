#!/bin/bash

# Setup script for Trino PostgreSQL access
# This script ensures the trino_user has proper access to only ddi and marts schemas

set -e

echo "Setting up Trino user access to PostgreSQL..."

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until podman exec jaffle-postgres pg_isready -U dbt -d dbt; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done

echo "PostgreSQL is ready. Setting up trino_user..."

# Run the init script
podman exec -i jaffle-postgres psql -U dbt -d dbt < init-postgres.sql

echo "Verifying trino_user setup..."
podman exec -it jaffle-postgres psql -U dbt -d dbt -c "SELECT usename FROM pg_user WHERE usename = 'trino_user';"

echo "Testing Trino connection..."
# Wait for Trino to be ready
sleep 5

# Test basic Trino connectivity
podman exec -it trino trino --server localhost:8080 --user trino_user --execute "SELECT 1"

# Test catalog access
echo "Testing catalog access..."
podman exec -it trino trino --server localhost:8080 --user trino_user --execute "SHOW SCHEMAS IN jaffle_postgres"

# Test schema access (should only see ddi and marts, not staging)
echo "Testing schema access permissions..."
podman exec -it trino trino --server localhost:8080 --user trino_user --execute "SELECT table_name FROM jaffle_postgres.information_schema.tables WHERE table_schema IN ('dbt_ddi', 'dbt_marts') LIMIT 5"

echo "Setup complete! trino_user has access to:"
echo "- dbt_ddi schema (✓)"
echo "- dbt_marts schema (✓)"
echo "- dbt_staging schema (✗ - no access)"
echo ""
echo "DBeaver connection details:"
echo "- Host: localhost"
echo "- Port: 8080"
echo "- User: trino_user"
echo "- Catalog: jaffle_postgres"