{% materialization external, adapter="duckdb", supported_languages=['sql', 'python'] %}
  {#
    Override of dbt-duckdb's external materialization that adds `format: iceberg` support.
    For iceberg, DuckDB's COPY ... TO ... (FORMAT ICEBERG, ALLOW_OVERWRITE TRUE) is used.
    The view is created via iceberg_scan() so downstream models can ref() this model.
  #}

  {%- set location = render(config.get('location', default=external_location(this, config))) -%})
  {%- set rendered_options = render_write_options(config) -%}

  {%- set format = config.get('format', 'parquet') | lower -%}
  {%- set allowed_formats = ['csv', 'parquet', 'json', 'iceberg'] -%}
  {%- if format not in allowed_formats -%}
    {{ exceptions.raise_compiler_error("Invalid format: " ~ format ~ ". Allowed formats are: " ~ allowed_formats | join(', ')) }}
  {%- endif -%}

  {# For non-iceberg, use the original options path #}
  {%- if format != 'iceberg' -%}
    {%- set write_options = adapter.external_write_options(location, rendered_options) -%}
    {%- set read_location = adapter.external_read_location(location, rendered_options) -%}
  {%- else -%}
    {%- set read_location = location -%}
  {%- endif -%}

  {%- set parquet_read_options = config.get('parquet_read_options', {'union_by_name': False}) -%}
  {%- set json_read_options = config.get('json_read_options', {'auto_detect': True}) -%}
  {%- set csv_read_options = config.get('csv_read_options', {'auto_detect': True}) -%}

  {%- set language = model['language'] -%}
  {%- set target_relation = this.incorporate(type='view') %}
  {%- set existing_relation = load_cached_relation(this) -%}
  {%- set temp_relation = make_intermediate_relation(this.incorporate(type='table'), suffix='__dbt_tmp') -%}
  {%- set intermediate_relation = make_intermediate_relation(target_relation, suffix='__dbt_int') -%}
  {%- set preexisting_temp_relation = load_cached_relation(temp_relation) -%}
  {%- set preexisting_intermediate_relation = load_cached_relation(intermediate_relation) -%}
  {%- set backup_relation_type = 'table' if existing_relation is none else existing_relation.type -%}
  {%- set backup_relation = make_backup_relation(target_relation, backup_relation_type) -%}
  {%- set preexisting_backup_relation = load_cached_relation(backup_relation) -%}
  {% set grant_config = config.get('grants') %}

  {{ drop_relation_if_exists(preexisting_intermediate_relation) }}
  {{ drop_relation_if_exists(preexisting_temp_relation) }}
  {{ drop_relation_if_exists(preexisting_backup_relation) }}

  {{ run_hooks(pre_hooks, inside_transaction=False) }}
  {{ run_hooks(pre_hooks, inside_transaction=True) }}

  -- build model into a temp table
  {% call statement('create_table', language=language) -%}
    {{- create_table_as(False, temp_relation, compiled_code, language) }}
  {%- endcall %}

  -- write temp table to the target format / location
  {% if format == 'iceberg' %}
    {% call statement('write_iceberg') -%}
      COPY {{ temp_relation }} TO '{{ location }}' (FORMAT ICEBERG, ALLOW_OVERWRITE TRUE)
    {%- endcall %}

    -- create a local DuckDB view over iceberg_scan for downstream ref()
    {% call statement('main', language='sql') -%}
      CREATE OR REPLACE VIEW {{ intermediate_relation }} AS (
        SELECT * FROM iceberg_scan('{{ read_location }}')
      )
    {%- endcall %}

  {% elif format == 'json' %}
    {{ write_to_file(temp_relation, location, write_options) }}
    {% call statement('main', language='sql') -%}
      CREATE OR REPLACE VIEW {{ intermediate_relation }} AS (
        SELECT * FROM read_json('{{ read_location }}'
        {%- for key, value in json_read_options.items() -%}
          , {{ key }}={{ "'" ~ value ~ "'" if value is string else value }}
        {%- endfor -%}
        )
      )
    {%- endcall %}

  {% elif format == 'parquet' %}
    {{ write_to_file(temp_relation, location, write_options) }}
    {% call statement('main', language='sql') -%}
      CREATE OR REPLACE VIEW {{ intermediate_relation }} AS (
        SELECT * FROM read_parquet('{{ read_location }}'
        {%- for key, value in parquet_read_options.items() -%}
          , {{ key }}={{ "'" ~ value ~ "'" if value is string else value }}
        {%- endfor -%}
        )
      )
    {%- endcall %}

  {% elif format == 'csv' %}
    {{ write_to_file(temp_relation, location, write_options) }}
    {% call statement('main', language='sql') -%}
      CREATE OR REPLACE VIEW {{ intermediate_relation }} AS (
        SELECT * FROM read_csv('{{ read_location }}'
        {%- for key, value in csv_read_options.items() -%}
          , {{ key }}={{ "'" ~ value ~ "'" if value is string else value }}
        {%- endfor -%}
        )
      )
    {%- endcall %}
  {% endif %}

  -- swap relations
  {% if existing_relation is not none %}
    {{ adapter.rename_relation(existing_relation, backup_relation) }}
  {% endif %}
  {{ adapter.rename_relation(intermediate_relation, target_relation) }}

  {{ run_hooks(post_hooks, inside_transaction=True) }}

  {% set should_revoke = should_revoke(existing_relation, full_refresh_mode=True) %}
  {% do apply_grants(target_relation, grant_config, should_revoke=should_revoke) %}
  {% do persist_docs(target_relation, model) %}

  {{ adapter.commit() }}

  {{ drop_relation_if_exists(backup_relation) }}
  {{ drop_relation_if_exists(temp_relation) }}

  {%- set plugin_name = config.get('plugin') -%}
  {% if plugin_name is not none %}
    {% do store_relation(plugin_name, target_relation, location, format, config) %}
  {% endif %}

  {{ run_hooks(post_hooks, inside_transaction=False) }}
  {{ return({'relations': [target_relation]}) }}

{% endmaterialization %}
