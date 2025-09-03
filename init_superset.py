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
        cursor.execute("SELECT id FROM dbs WHERE database_name = %s", ('dbt',))
        if cursor.fetchone():
            print("Database 'dbt' already exists in Superset")
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

if __name__ == "__main__":
    print("Attempting to add dbt database to Superset...")

    # Try CLI method first
    if add_dbt_database():
        sys.exit(0)

    # Fallback to direct SQL
    print("CLI method failed, trying fallback...")
    if add_dbt_database_fallback():
        sys.exit(0)

    print("All methods failed to add database")
    sys.exit(1)