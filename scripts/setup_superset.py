#!/usr/bin/env python3
"""
Idempotent Superset setup: creates a Trino database connection, DDI datasets,
charts, and a dashboard backed by the Iceberg lakehouse via Trino.

Safe to re-run: existing resources are detected and reused.
"""

import json
import sys

import requests

SUPERSET_URL = "http://localhost:8088"
TRINO_URI = "trino://trino_user@trino:8080/lakehouse"
DB_NAME = "Trino Lakehouse"
DASHBOARD_TITLE = "Rolling Sales Dashboard (Trino/Iceberg)"


class SupersetClient:
    def __init__(self, username="admin", password="admin"):
        self.base = SUPERSET_URL
        self.session = requests.Session()
        self._login(username, password)

    def _login(self, username, password):
        resp = self.session.post(
            f"{self.base}/api/v1/security/login",
            json={"username": username, "password": password, "provider": "db", "refresh": True},
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {token}"})

        csrf_resp = self.session.get(f"{self.base}/api/v1/security/csrf_token/")
        csrf_resp.raise_for_status()
        csrf = csrf_resp.json()["result"]
        self.session.headers.update({"X-CSRFToken": csrf, "Referer": self.base})

    def get(self, path, **kwargs):
        return self.session.get(f"{self.base}{path}", **kwargs)

    def post(self, path, **kwargs):
        return self.session.post(f"{self.base}{path}", **kwargs)

    def put(self, path, **kwargs):
        return self.session.put(f"{self.base}{path}", **kwargs)


def find_resource(client, list_path, name_field, name_value, page_size=100):
    resp = client.get(f"{list_path}?q=(page_size:{page_size})")
    resp.raise_for_status()
    for item in resp.json().get("result", []):
        if item.get(name_field) == name_value:
            return item
    return None


def ensure_database(client):
    existing = find_resource(client, "/api/v1/database/", "database_name", DB_NAME)
    if existing:
        print(f"  [skip] database '{DB_NAME}' already exists (id={existing['id']})")
        return existing["id"]

    resp = client.post(
        "/api/v1/database/",
        json={
            "database_name": DB_NAME,
            "sqlalchemy_uri": TRINO_URI,
            "expose_in_sqllab": True,
            "allow_run_async": False,
            "allow_ctas": False,
            "allow_cvas": False,
            "allow_dml": False,
        },
    )
    if resp.status_code != 201:
        print(f"  [error] creating database: {resp.text}")
        sys.exit(1)
    db_id = resp.json()["id"]
    print(f"  [created] database '{DB_NAME}' (id={db_id})")
    return db_id


def ensure_dataset(client, db_id, schema, table):
    resp = client.get("/api/v1/dataset/?q=(page_size:100)")
    resp.raise_for_status()
    datasets = resp.json().get("result", [])

    # Already pointing at the right database
    for ds in datasets:
        if ds["table_name"] == table and ds.get("schema") == schema and ds["database"]["id"] == db_id:
            print(f"  [skip] dataset '{schema}.{table}' already exists (id={ds['id']})")
            return ds["id"]

    # Same table name exists but pointing at wrong database — migrate it
    for ds in datasets:
        if ds["table_name"] == table:
            ds_id = ds["id"]
            resp = client.put(
                f"/api/v1/dataset/{ds_id}",
                json={"database_id": db_id, "schema": schema, "table_name": table},
            )
            if resp.status_code in (200, 201):
                print(f"  [migrated] dataset '{table}' id={ds_id} → {schema} on db {db_id}")
                return ds_id
            print(f"  [error] migrating dataset {table}: {resp.text}")
            return None

    resp = client.post(
        "/api/v1/dataset/",
        json={"database": db_id, "schema": schema, "table_name": table},
    )
    if resp.status_code != 201:
        print(f"  [error] creating dataset {schema}.{table}: {resp.text}")
        return None
    ds_id = resp.json()["id"]
    print(f"  [created] dataset '{schema}.{table}' (id={ds_id})")
    return ds_id


def ensure_chart(client, name, datasource_id, viz_type, params_dict):
    existing = find_resource(client, "/api/v1/chart/", "slice_name", name)
    if existing:
        print(f"  [skip] chart '{name}' already exists (id={existing['id']})")
        return existing["id"]

    resp = client.post(
        "/api/v1/chart/",
        json={
            "slice_name": name,
            "datasource_id": datasource_id,
            "datasource_type": "table",
            "viz_type": viz_type,
            "params": json.dumps(params_dict),
        },
    )
    if resp.status_code != 201:
        print(f"  [error] creating chart '{name}': {resp.text}")
        return None
    chart_id = resp.json()["id"]
    print(f"  [created] chart '{name}' (id={chart_id})")
    return chart_id


def ensure_dashboard(client, title, chart_ids):
    existing = find_resource(client, "/api/v1/dashboard/", "dashboard_title", title)
    if existing:
        print(f"  [skip] dashboard '{title}' already exists (id={existing['id']})")
        return existing["id"]

    # Build a simple grid layout for the charts
    grid_children = []
    col = 0
    for i, cid in enumerate(chart_ids):
        grid_children.append({
            "id": f"CHART-{i}",
            "type": "CHART",
            "children": [],
            "meta": {"chartId": cid, "width": 6, "height": 50, "sliceName": f"Chart {i}"},
        })
        col += 6

    position = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [f"ROW-0"], "parents": ["ROOT_ID"]},
        "ROW-0": {
            "type": "ROW",
            "id": "ROW-0",
            "children": [f"CHART-{i}" for i in range(len(chart_ids))],
            "parents": ["ROOT_ID", "GRID_ID"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        },
    }
    for i, item in enumerate(grid_children):
        item["parents"] = ["ROOT_ID", "GRID_ID", "ROW-0"]
        position[f"CHART-{i}"] = item

    resp = client.post(
        "/api/v1/dashboard/",
        json={
            "dashboard_title": title,
            "position_json": json.dumps(position),
        },
    )
    if resp.status_code != 201:
        print(f"  [error] creating dashboard: {resp.text}")
        return None
    dash_id = resp.json()["id"]
    print(f"  [created] dashboard '{title}' (id={dash_id})")
    return dash_id


def main():
    print("==> Connecting to Superset...")
    client = SupersetClient()

    print("==> Database connection")
    db_id = ensure_database(client)

    print("==> Datasets")
    ds_orders = ensure_dataset(client, db_id, "ddi", "rolling_30_day_orders")
    ds_at_risk = ensure_dataset(client, db_id, "ddi", "at_risk_customers")

    print("==> Charts")
    chart_ids = []

    cid = ensure_chart(
        client,
        "Rolling 30-Day Order Amounts (Trino/Iceberg)",
        ds_orders,
        "table",
        {
            "all_columns": ["order_date", "total_amount", "rolling_30_day_amount", "rolling_30_day_avg_daily"],
            "order_by_cols": [],
            "row_limit": 50,
        },
    )
    if cid:
        chart_ids.append(cid)

    cid = ensure_chart(
        client,
        "At-Risk Customers (Trino/Iceberg)",
        ds_at_risk,
        "table",
        {
            "all_columns": ["customer_id", "first_name", "last_name", "days_since_last_order", "completed_orders"],
            "order_by_cols": [],
            "row_limit": 100,
        },
    )
    if cid:
        chart_ids.append(cid)

    print("==> Dashboard")
    if chart_ids:
        ensure_dashboard(client, DASHBOARD_TITLE, chart_ids)
    else:
        print("  [skip] no charts created, skipping dashboard")

    print("\nSuperset setup complete.")
    print(f"  Dashboard: {SUPERSET_URL}/superset/dashboard/")
    print(f"  SQL Lab:   {SUPERSET_URL}/superset/sqllab/")


if __name__ == "__main__":
    main()
