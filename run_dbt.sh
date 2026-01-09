#!/bin/bash
# Helper script to run dbt commands with the correct virtual environment

# Activate the project's virtual environment
source .venv/bin/activate

# Run dbt with all arguments passed to this script
.venv/bin/dbt "$@" --profiles-dir .

# Deactivate is automatic when script exits
