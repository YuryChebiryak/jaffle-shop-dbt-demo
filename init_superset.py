#!/usr/bin/env python3

import os
import sys
import time
import subprocess

# Use Superset CLI to add the database connection
def add_dbt_database():
    try:
        # Use superset CLI to add the database
        cmd = [
            "superset", "set-database-uri",
            "--database-name", "dbt",
            "--uri", "postgresql://dbt:dbt@postgres:5432/dbt"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            print("Successfully added 'dbt' database to Superset using CLI")
            return True
        else:
            print(f"CLI command failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("CLI command timed out")
        return False
    except Exception as e:
        print(f"Error running CLI command: {e}")
        return False

# Alternative method using direct database insertion
def add_dbt_database_fallback():
    try:
        import psycopg2
        from psycopg2 import sql

        # Connect to Superset's database
        conn = psycopg2.connect(os.environ['SQLALCHEMY_DATABASE_URI'])
        conn.autocommit = True
        cursor = conn.cursor()

        # Check if database already exists
        cursor.execute("SELECT id, sqlalchemy_uri FROM dbs WHERE database_name = %s", ('dbt',))
        existing = cursor.fetchone()
        if existing:
            db_id, current_uri = existing
            expected_uri = 'postgresql://dbt:dbt@postgres:5432/dbt'
            if current_uri == expected_uri:
                print("Database 'dbt' already exists in Superset with correct URI")
                cursor.close()
                conn.close()
                return True
            else:
                # Update the URI
                cursor.execute("UPDATE dbs SET sqlalchemy_uri = %s, changed_on = NOW() WHERE id = %s", (expected_uri, db_id))
                print("Updated database 'dbt' URI in Superset")
                cursor.close()
                conn.close()
                return True

        # Insert the database connection
        insert_query = """
        INSERT INTO dbs (
            database_name,
            sqlalchemy_uri,
            created_on,
            changed_on,
            created_by_fk,
            changed_by_fk
        ) VALUES (
            'dbt',
            'postgresql://dbt:dbt@postgres:5432/dbt',
            NOW(),
            NOW(),
            1,
            1
        )
        """

        cursor.execute(insert_query)
        print("Successfully added 'dbt' database to Superset using direct SQL")
        cursor.close()
        conn.close()
        return True

    except ImportError:
        print("psycopg2 not available, skipping fallback method")
        return False
    except Exception as e:
        print(f"Error in fallback method: {e}")
        return False

def add_dataset():
    try:
        from superset.app import create_app
        from superset import db
        from superset.models.core import Database
        from superset.datasets.models import Dataset

        app = create_app()
        with app.app_context():
            database = db.session.query(Database).filter_by(database_name='dbt').first()
            if not database:
                print("Database 'dbt' not found for dataset creation")
                return False

            # Check if dataset exists
            existing = db.session.query(Dataset).filter_by(
                database_id=database.id,
                schema='ddi',
                table_name='rolling_30_day_orders'
            ).first()
            if existing:
                print("Dataset for ddi.rolling_30_day_orders already exists")
                return True

            # Create dataset
            dataset = Dataset(
                database_id=database.id,
                schema='ddi',
                table_name='rolling_30_day_orders',
                owners=[],
                created_by_fk=1,
                changed_by_fk=1
            )
            db.session.add(dataset)
            db.session.commit()
            print("Successfully added dataset for ddi.rolling_30_day_orders")
            return True
    except Exception as e:
        print(f"Error adding dataset: {e}")
        return False

if __name__ == "__main__":
    print("Attempting to add dbt database to Superset...")

    # Try CLI method first
    if add_dbt_database():
        add_dataset()
        sys.exit(0)

    # Fallback to direct SQL
    print("CLI method failed, trying fallback...")
    if add_dbt_database_fallback():
        add_dataset()
        sys.exit(0)

    print("All methods failed to add database")
    sys.exit(1)