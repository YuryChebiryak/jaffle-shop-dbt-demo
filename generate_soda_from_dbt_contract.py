import yaml
import sys

def main(contract_path="models/ddi/schema.yml", model_name="rolling_30_day_orders", output_path="soda_checks_rolling_30_day_orders.yml", datasource_name="jaffle_shop_datasource", table_name="dbt_ddi.rolling_30_day_orders"):
    with open(contract_path) as f:
        schema = yaml.safe_load(f)

    models = schema["models"]
    model = next((m for m in models if m["name"] == model_name), None)
    if not model:
        print(f"Model {model_name} not found in {contract_path}")
        sys.exit(1)

    checks = [
        {
            "row_count > 0": {
                "name": "Has some rows"
            }
        }
    ]

    for col_def in model["columns"]:
        col_name = col_def["name"]
        tests = col_def.get("tests", [])

        # Handle string tests like 'not_null', 'unique'
        string_tests = [t for t in tests if isinstance(t, str)]
        for test in string_tests:
            if test == "not_null":
                checks.append(
                    {
                        f"missing_count({col_name}) = 0": {
                            "name": f"No missing values in {col_name}"
                        }
                    }
                )
            elif test == "unique":
                checks.append(
                    {
                        f"duplicate_count({col_name}) = 0": {
                            "name": f"No duplicates in {col_name}"
                        }
                    }
                )

        # Handle dict tests like accepted_values, dbt_expectations
        dict_tests = [t for t in tests if isinstance(t, dict)]
        for test_dict in dict_tests:
            test_name = list(test_dict.keys())[0]
            test_args = test_dict[test_name].get("arguments", {})

            if test_name == "accepted_values":
                values = test_args.get("values", [])
                checks.append(
                    {
                        f"invalid_percent({col_name}) = 0": {
                            "name": f"{col_name} values are accepted",
                            "valid values": values
                        }
                    }
                )
            elif "dbt_expectations.expect_column_values_to_be_between" == test_name:
                min_value = test_args.get("min_value")
                max_value = test_args.get("max_value")
                if min_value is not None:
                    checks.append(
                        {
                            f"min({col_name}) >= {min_value}": {
                                "name": f"{col_name} min {min_value}"
                            }
                        }
                    )
                if max_value is not None:
                    checks.append(
                        {
                            f"max({col_name}) <= {max_value}": {
                                "name": f"{col_name} max {max_value}"
                            }
                        }
                    )

    sodacl_yaml = {
        f"checks for {table_name}": checks,
    }

    with open(output_path, "w") as f:
        yaml.dump(
            sodacl_yaml, f, default_flow_style=False, sort_keys=False
        )

    print(f"Generated {output_path} with {len(checks)} checks for model {model_name}")

if __name__ == "__main__":
    # Generate for rolling_30_day_orders
    main(
        contract_path="models/ddi/schema.yml",
        model_name="rolling_30_day_orders",
        output_path="soda_checks_rolling_30_day_orders.yml",
        table_name="dbt_ddi.rolling_30_day_orders"
    )
    
    # Generate for at_risk_customers
    main(
        contract_path="models/ddi/schema.yml",
        model_name="at_risk_customers",
        output_path="soda_checks_at_risk_customers.yml",
        table_name="dbt_ddi.at_risk_customers"
    )