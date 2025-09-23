#!/bin/bash
python -m pip install psycopg2-binary
export PYTHONPATH=/app/superset_home/.local/lib/python3.10/site-packages:$PYTHONPATH
superset db upgrade
superset fab create-admin --username data_analyst --firstname Data --lastname Analyst --email analyst@example.com --password analyst
superset init
python3 /app/init_superset.py
superset run -h 0.0.0.0 -p 8088