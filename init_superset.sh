#!/bin/bash
/app/.venv/bin/pip install psycopg2-binary
superset db upgrade
superset fab create-admin --username data_analyst --firstname Data --lastname Analyst --email analyst@example.com --password analyst
superset init
python3 /app/init_superset.py
superset run -h 0.0.0.0 -p 8088