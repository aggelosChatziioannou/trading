"""
Database initialization script.

Creates the database and runs the schema SQL to set up all tables.
Requires TimescaleDB to be running (via docker-compose).
"""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg2

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings


def init_database() -> None:
    """Create tables from schemas.sql."""
    schema_path = Path(__file__).resolve().parent.parent / "data" / "storage" / "schemas.sql"
    schema_sql = schema_path.read_text()

    print(f"Connecting to {settings.db.host}:{settings.db.port}/{settings.db.name}...")

    try:
        conn = psycopg2.connect(
            host=settings.db.host,
            port=settings.db.port,
            dbname=settings.db.name,
            user=settings.db.user,
            password=settings.db.password,
        )
        conn.autocommit = True

        with conn.cursor() as cur:
            cur.execute(schema_sql)

        conn.close()
        print("Database initialized successfully.")
        print("Tables created: candles, news, features, trades, hypotheses, signals, risk_events")

    except psycopg2.OperationalError as e:
        print(f"Connection failed: {e}")
        print("\nMake sure TimescaleDB is running:")
        print("  cd trading-system && docker-compose up -d")
        sys.exit(1)


if __name__ == "__main__":
    init_database()
