-- Create Trino user with limited access to dbt_ddi and dbt_marts schemas
CREATE ROLE trino_user LOGIN PASSWORD 'trino_pass';
GRANT USAGE ON SCHEMA dbt_ddi TO trino_user;
GRANT SELECT ON ALL TABLES IN SCHEMA dbt_ddi TO trino_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA dbt_ddi GRANT SELECT ON TABLES TO trino_user;
GRANT USAGE ON SCHEMA dbt_marts TO trino_user;
GRANT SELECT ON ALL TABLES IN SCHEMA dbt_marts TO trino_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA dbt_marts GRANT SELECT ON TABLES TO trino_user;