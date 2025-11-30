{% macro validate_contracts() %}
    {# Get all models with the 'serving' tag #}
    {% set models_to_validate = [] %}
    {% for node in graph.nodes.values() | selectattr("resource_type", "equalto", "model") %}
        {% if 'serving' in node.config.tags and node.config.contract.enforced %}
            {% do models_to_validate.append(node) %}
        {% endif %}
    {% endfor %}

    {% if models_to_validate | length == 0 %}
        {{ log("No models found with tag 'serving' and enforced contract.", info=True) }}
        {{ return(None) }}
    {% endif %}

    {% set validation_errors = [] %}

    {% for model_node in models_to_validate %}
        {% set relation = adapter.get_relation(
            database=model_node.database,
            schema=model_node.schema,
            identifier=model_node.alias
        ) %}

        {% if relation is none %}
             {% do validation_errors.append("Relation not found for model: " ~ model_node.name) %}
        {% else %}
            {# Fetch runtime columns from the database #}
            {% set runtime_columns = adapter.get_columns_in_relation(relation) %}
            {% set runtime_col_dict = {} %}
            {% for col in runtime_columns %}
                {% do runtime_col_dict.update({col.name.lower(): col.dtype.lower()}) %}
            {% endfor %}

            {# Fetch contract columns from the model configuration #}
            {% set contract_columns = model_node.columns %}
            {% set contract_col_dict = {} %}
            {% for col_name, col_def in contract_columns.items() %}
                {% if col_def.data_type %}
                    {% do contract_col_dict.update({col_name.lower(): col_def.data_type.lower()}) %}
                {% endif %}
            {% endfor %}

            {% set missing_columns = [] %}
            {% set extra_columns = [] %}
            {% set type_mismatches = [] %}
            
            {# Type mapping for normalization #}
            {% set type_mapping = {
                'character varying': 'varchar',
                'numeric': 'decimal',
                'integer': 'int',
                'text': 'varchar'
            } %}

            {# Check for missing columns and type mismatches #}
            {% for col_name, contract_type in contract_col_dict.items() %}
                {% if col_name not in runtime_col_dict %}
                    {% do missing_columns.append(col_name) %}
                {% else %}
                    {% set runtime_type = runtime_col_dict[col_name] %}
                    
                    {# Normalize runtime type #}
                    {% set runtime_type_norm = type_mapping.get(runtime_type, runtime_type) %}
                    
                    {# Normalize contract type: strip parameters and map synonyms #}
                    {% set contract_type_base = contract_type.split('(')[0] %}
                    {% set contract_type_norm = type_mapping.get(contract_type_base, contract_type_base) %}
                    
                    {# Strict comparison of normalized data types #}
                    {% if contract_type_norm != runtime_type_norm %}
                        {% do type_mismatches.append("Column '" ~ col_name ~ "' type mismatch: contract='" ~ contract_type ~ "' (norm: " ~ contract_type_norm ~ "), database='" ~ runtime_type ~ "' (norm: " ~ runtime_type_norm ~ ")") %}
                    {% endif %}
                {% endif %}
            {% endfor %}

            {# Check for extra columns #}
            {% for col_name in runtime_col_dict.keys() %}
                {% if col_name not in contract_col_dict %}
                    {% do extra_columns.append(col_name) %}
                {% endif %}
            {% endfor %}

            {# Collect errors #}
            {% if missing_columns | length > 0 or extra_columns | length > 0 or type_mismatches | length > 0 %}
                {% set error_msg = "Data Contract Validation Failed for " ~ model_node.name ~ ":\n" %}
                {% if missing_columns | length > 0 %}
                    {% set error_msg = error_msg ~ "  Missing columns: " ~ missing_columns | join(", ") ~ "\n" %}
                {% endif %}
                {% if extra_columns | length > 0 %}
                    {% set error_msg = error_msg ~ "  Extra columns: " ~ extra_columns | join(", ") ~ "\n" %}
                {% endif %}
                {% if type_mismatches | length > 0 %}
                    {% set error_msg = error_msg ~ "  Type mismatches:\n    " ~ type_mismatches | join("\n    ") ~ "\n" %}
                {% endif %}
                {% do validation_errors.append(error_msg) %}
            {% else %}
                {{ log("Data Contract Validation Passed for " ~ model_node.name, info=True) }}
            {% endif %}
        {% endif %}
    {% endfor %}

    {% if validation_errors | length > 0 %}
        {{ exceptions.raise_compiler_error(validation_errors | join("\n")) }}
    {% endif %}

{% endmacro %}