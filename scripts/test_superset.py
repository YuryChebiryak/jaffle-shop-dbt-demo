#!/usr/bin/env python3
"""
Smoke test for Superset → Trino → Iceberg integration.

Checks:
  1. Superset health endpoint responds
  2. Admin can log in
  3. data_analyst user can log in
  4. Trino Lakehouse database connection is registered
  5. DDI datasets exist (rolling_30_day_orders, at_risk_customers)
  6. Dashboard exists
  7. SQL query via Superset SQL Lab reaches Trino and returns rows
     (verifies the full Superset → Trino → Iceberg path)

Exit 0 on success, exit 1 on any failure.
"""

import sys
import time

import requests

SUPERSET_URL = "http://localhost:8088"
DB_NAME = "Trino Lakehouse"
DASHBOARD_TITLE = "Rolling Sales Dashboard (Trino/Iceberg)"
PROBE_SQL = "SELECT order_date, rolling_30_day_amount FROM ddi.rolling_30_day_orders LIMIT 5"

PASS = "PASS"
FAIL = "FAIL"
failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"  [{PASS}] {label}")
    else:
        print(f"  [{FAIL}] {label}" + (f": {detail}" if detail else ""))
        failures.append(label)


class SupersetClient:
    def __init__(self, username, password):
        self.base = SUPERSET_URL
        self.session = requests.Session()
        self.token = None
        resp = self.session.post(
            f"{self.base}/api/v1/security/login",
            json={"username": username, "password": password, "provider": "db", "refresh": True},
            timeout=10,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"login failed ({resp.status_code}): {resp.text[:200]}")
        self.token = resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

        csrf = self.session.get(f"{self.base}/api/v1/security/csrf_token/", timeout=10)
        csrf.raise_for_status()
        self.session.headers.update({
            "X-CSRFToken": csrf.json()["result"],
            "Referer": self.base,
        })

    def get(self, path, **kw):
        return self.session.get(f"{self.base}{path}", timeout=15, **kw)

    def post(self, path, **kw):
        return self.session.post(f"{self.base}{path}", timeout=30, **kw)


def wait_for_superset(timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{SUPERSET_URL}/health", timeout=5)
            if r.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(2)
    return False


def find_by_name(client, list_path, name_field, name_value):
    resp = client.get(f"{list_path}?q=(page_size:200)")
    if resp.status_code != 200:
        return None
    for item in resp.json().get("result", []):
        if item.get(name_field) == name_value:
            return item
    return None


def main():
    print("==> Superset integration tests")
    print()

    # 1. Health
    print("-- Health")
    alive = wait_for_superset()
    check("Superset /health responds 200", alive)
    if not alive:
        print("\nSuperset is unreachable. Aborting.")
        sys.exit(1)

    # 2. Admin login
    print("\n-- Authentication")
    try:
        admin = SupersetClient("admin", "admin")
        check("Admin login (JWT)", True)
    except Exception as e:
        check("Admin login (JWT)", False, str(e))
        print("\nCannot authenticate. Aborting.")
        sys.exit(1)

    # 3. data_analyst login
    try:
        SupersetClient("data_analyst", "analyst")
        check("data_analyst login (JWT)", True)
    except Exception as e:
        check("data_analyst login (JWT)", False, str(e))

    # 4. Trino database connection
    print("\n-- Database connection")
    db = find_by_name(admin, "/api/v1/database/", "database_name", DB_NAME)
    check(f"Database '{DB_NAME}' registered", db is not None)
    if db:
        # Ping Trino by running SELECT 1 via SQL Lab
        resp = admin.post(
            "/api/v1/sqllab/execute/",
            json={"database_id": db["id"], "sql": "SELECT 1 AS ping", "runAsync": False},
        )
        ok = resp.status_code == 200 and resp.json().get("data")
        check(
            "Trino connection is reachable from Superset (SELECT 1)",
            ok,
            resp.text[:200] if not ok else "",
        )

    # 5. Datasets
    print("\n-- Datasets")
    for table in ("rolling_30_day_orders", "at_risk_customers"):
        resp = admin.get("/api/v1/dataset/?q=(page_size:200)")
        found = any(
            ds["table_name"] == table and ds["database"]["id"] == (db["id"] if db else -1)
            for ds in resp.json().get("result", [])
        )
        check(f"Dataset '{table}' exists (Trino/Iceberg)", found)

    # 6. Dashboard
    print("\n-- Dashboard")
    dash = find_by_name(admin, "/api/v1/dashboard/", "dashboard_title", DASHBOARD_TITLE)
    check(f"Dashboard '{DASHBOARD_TITLE}' exists", dash is not None)

    # 7. End-to-end SQL via Superset SQL Lab → Trino → Iceberg
    print("\n-- End-to-end query (Superset → Trino → Iceberg)")
    if db:
        resp = admin.post(
            "/api/v1/sqllab/execute/",
            json={
                "database_id": db["id"],
                "sql": PROBE_SQL,
                "runAsync": False,
                "select_as_cta": False,
            },
        )
        ok = resp.status_code == 200 and "data" in resp.json()
        rows = len(resp.json().get("data", [])) if ok else 0
        check(
            f"SQL Lab query returns rows from Trino (got {rows})",
            ok and rows > 0,
            resp.text[:300] if not ok else "",
        )
    else:
        check("SQL Lab query (skipped, no DB connection)", False, "no Trino database registered")

    # Summary
    print()
    if failures:
        print(f"FAILED ({len(failures)} check(s)):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("All checks passed.")


if __name__ == "__main__":
    main()
