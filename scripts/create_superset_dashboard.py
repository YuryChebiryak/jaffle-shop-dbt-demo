#!/usr/bin/env python3

import os
import sys
import time
import requests
from requests.auth import HTTPBasicAuth

# Superset configuration
SUPERSET_URL = "http://localhost:8088"
ADMIN_USER = "admin"
ADMIN_PASSWORD = "admin"

# Database and table info
DATABASE_NAME = "dbt"
SCHEMA_NAME = "ddi"
TABLE_NAME = "rolling_30_day_orders"

def get_superset_session():
    """Get authenticated session with Superset"""
    session = requests.Session()
    session.auth = HTTPBasicAuth(ADMIN_USER, ADMIN_PASSWORD)
    return session

def create_dataset(session):
    """Create a dataset from the rolling_30_day_orders table"""
    dataset_payload = {
        "database": 1,  # Assuming dbt database is the first one
        "schema": SCHEMA_NAME,
        "table_name": TABLE_NAME
    }

    response = session.post(f"{SUPERSET_URL}/api/v1/dataset/", json=dataset_payload)

    if response.status_code == 201:
        dataset = response.json()
        print(f"✅ Created dataset: {dataset['result']['table_name']}")
        return dataset['result']['id']
    elif response.status_code == 422:
        # Dataset might already exist, try to find it
        print("⚠️  Dataset might already exist, trying to find it...")
        return find_existing_dataset(session)
    else:
        print(f"❌ Failed to create dataset: {response.text}")
        return None

def find_existing_dataset(session):
    """Find existing dataset by name"""
    response = session.get(f"{SUPERSET_URL}/api/v1/dataset/")

    if response.status_code == 200:
        datasets = response.json()['result']
        for dataset in datasets:
            if dataset['table_name'] == TABLE_NAME and dataset['schema'] == SCHEMA_NAME:
                print(f"✅ Found existing dataset: {dataset['table_name']}")
                return dataset['id']

    print("❌ Could not find existing dataset")
    return None

def create_line_chart(session, dataset_id):
    """Create a line chart for rolling 30-day amounts"""
    chart_payload = {
        "slice_name": "Rolling 30-Day Order Amounts",
        "description": "Trend of rolling 30-day order amounts over time",
        "datasource_id": dataset_id,
        "datasource_type": "table",
        "viz_type": "line",
        "params": {
            "metrics": ["rolling_30_day_amount"],
            "groupby": ["order_date"],
            "time_grain_sqla": "P1D",
            "row_limit": 50,
            "show_legend": True,
            "rich_tooltip": True,
            "y_axis_format": ".2f",
            "x_axis_label": "Date",
            "y_axis_label": "Rolling 30-Day Amount ($)"
        }
    }

    response = session.post(f"{SUPERSET_URL}/api/v1/chart/", json=chart_payload)

    if response.status_code == 201:
        chart = response.json()
        print(f"✅ Created line chart: {chart['result']['slice_name']}")
        return chart['result']['id']
    else:
        print(f"❌ Failed to create line chart: {response.text}")
        return None

def create_bar_chart(session, dataset_id):
    """Create a bar chart for daily amounts"""
    chart_payload = {
        "slice_name": "Daily Order Amounts",
        "description": "Daily order amounts with order counts",
        "datasource_id": dataset_id,
        "datasource_type": "table",
        "viz_type": "bar",
        "params": {
            "metrics": ["total_amount", "order_count"],
            "groupby": ["order_date"],
            "time_grain_sqla": "P1D",
            "row_limit": 50,
            "show_legend": True,
            "rich_tooltip": True,
            "y_axis_format": ".2f",
            "x_axis_label": "Date",
            "y_axis_label": "Amount / Count"
        }
    }

    response = session.post(f"{SUPERSET_URL}/api/v1/chart/", json=chart_payload)

    if response.status_code == 201:
        chart = response.json()
        print(f"✅ Created bar chart: {chart['result']['slice_name']}")
        return chart['result']['id']
    else:
        print(f"❌ Failed to create bar chart: {response.text}")
        return None

def create_area_chart(session, dataset_id):
    """Create an area chart for rolling averages"""
    chart_payload = {
        "slice_name": "Rolling 30-Day Average Daily Amount",
        "description": "Rolling 30-day average of daily order amounts",
        "datasource_id": dataset_id,
        "datasource_type": "table",
        "viz_type": "area",
        "params": {
            "metrics": ["rolling_30_day_avg_daily"],
            "groupby": ["order_date"],
            "time_grain_sqla": "P1D",
            "row_limit": 50,
            "show_legend": True,
            "rich_tooltip": True,
            "y_axis_format": ".2f",
            "x_axis_label": "Date",
            "y_axis_label": "Average Daily Amount ($)"
        }
    }

    response = session.post(f"{SUPERSET_URL}/api/v1/chart/", json=chart_payload)

    if response.status_code == 201:
        chart = response.json()
        print(f"✅ Created area chart: {chart['result']['slice_name']}")
        return chart['result']['id']
    else:
        print(f"❌ Failed to create area chart: {response.text}")
        return None

def create_dashboard(session, chart_ids):
    """Create a dashboard with the charts"""
    dashboard_payload = {
        "dashboard_title": "Rolling 30-Day Orders Analytics",
        "description": "Dashboard showing rolling 30-day order trends and analytics",
        "position_json": {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": "ROOT_ID",
            "children": [
                {
                    "id": "CHART-1",
                    "type": "CHART",
                    "meta": {
                        "chartId": chart_ids[0],
                        "width": 6,
                        "height": 4
                    }
                },
                {
                    "id": "CHART-2",
                    "type": "CHART",
                    "meta": {
                        "chartId": chart_ids[1],
                        "width": 6,
                        "height": 4
                    }
                },
                {
                    "id": "CHART-3",
                    "type": "CHART",
                    "meta": {
                        "chartId": chart_ids[2],
                        "width": 12,
                        "height": 4
                    }
                }
            ]
        }
    }

    response = session.post(f"{SUPERSET_URL}/api/v1/dashboard/", json=dashboard_payload)

    if response.status_code == 201:
        dashboard = response.json()
        print(f"✅ Created dashboard: {dashboard['result']['dashboard_title']}")
        print(f"📊 Dashboard URL: {SUPERSET_URL}/superset/dashboard/{dashboard['result']['id']}/")
        return dashboard['result']['id']
    else:
        print(f"❌ Failed to create dashboard: {response.text}")
        return None

def main():
    print("🚀 Creating Superset dashboard for Rolling 30-Day Orders...")

    # Wait for Superset to be ready
    print("⏳ Waiting for Superset to be ready...")
    time.sleep(10)

    session = get_superset_session()

    # Create dataset
    dataset_id = create_dataset(session)
    if not dataset_id:
        print("❌ Failed to create/find dataset. Exiting.")
        sys.exit(1)

    # Create charts
    line_chart_id = create_line_chart(session, dataset_id)
    bar_chart_id = create_bar_chart(session, dataset_id)
    area_chart_id = create_area_chart(session, dataset_id)

    if not all([line_chart_id, bar_chart_id, area_chart_id]):
        print("❌ Failed to create all charts. Exiting.")
        sys.exit(1)

    # Create dashboard
    chart_ids = [line_chart_id, bar_chart_id, area_chart_id]
    dashboard_id = create_dashboard(session, chart_ids)

    if dashboard_id:
        print("\n🎉 Dashboard creation completed successfully!")
        print("📈 Your rolling 30-day orders analytics dashboard is ready!")
    else:
        print("❌ Dashboard creation failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()