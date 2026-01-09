# Trino-Iceberg Migration Plan

## System of Record Definition

The new system of record will be the Iceberg catalog managed by Trino. Trino acts as the unified compute engine, executing dbt transformations and serving queries, while Iceberg provides the persistent storage layer with ACID transactions, schema evolution, and time travel capabilities. Metadata is stored in the Iceberg catalog, which can be backed by Hive Metastore or other catalog services, ensuring state consistency across the lakehouse architecture. Trino manages the metadata through its catalog interface, allowing for centralized governance and lineage tracking.

## dbt Profile Configuration

Update `profiles.yml` to use the `dbt-trino` adapter instead of `dbt-postgres`. The profile should specify:
- type: trino
- host: Trino coordinator host
- port: Trino port (default 8080)
- catalog: The Iceberg catalog name (e.g., iceberg)
- schema: Target schema within the catalog
- user: Authentication user
- password: Authentication password
- threads: Number of threads for parallel execution

## Materialization Strategy

In `dbt_project.yml`, set global defaults:
- +materialized: table (to ensure all models create Iceberg tables)
- +format: iceberg (if supported by dbt-trino adapter)

Model-level configurations can override as needed, but staging layers may use ephemeral or view materializations for intermediate processing before final table materialization in marts and ddi layers.

## Trino Catalog Configuration

Create `iceberg.properties` in Trino's catalog directory with:
- connector.name=iceberg
- iceberg.catalog.type: hive (or glue, nessie depending on metastore)
- hive.metastore.uri: URI to Hive Metastore
- fs.native-s3.enabled: true (for S3/MinIO)
- s3.endpoint: MinIO endpoint
- s3.access-key: Access key
- s3.secret-key: Secret key
- s3.path-style-access: true

This configuration enables Trino to read/write Iceberg tables stored on S3-compatible object storage.

## Data Flow Narrative

1. CSV files are ingested via `dbt seed`, creating initial Iceberg tables in the raw layer within the Trino catalog.
2. Staging models transform raw data using Trino's compute engine, materializing intermediate views or tables as needed.
3. Marts and DDI models aggregate and derive insights, materializing as Iceberg tables for persistent storage.
4. End-users access data through Trino queries, with DBeaver and Superset connecting directly to the Iceberg catalog via Trino's JDBC interface.
5. All transformations maintain ACID properties through Iceberg's transactional guarantees, ensuring data consistency.