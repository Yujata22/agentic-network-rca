"""
Small, deliberately-minimal Postgres helper.

This is provided so you don't have to spend your limited time on database
boilerplate -- feel free to use it as-is, wrap it, or replace it entirely
with your own connection handling / ORM of choice. Nothing about your agent
architecture should depend on this specific helper.
"""
from __future__ import annotations

import os
import json
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://rca_user:rca_password@postgres:5432/network_rca"
)


@contextmanager
def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()


def run_query(sql: str, params: tuple | dict | None = None) -> list[dict[str, Any]]:
    """
    Executes a read-only SQL query and returns a list of plain dicts.
    JSONB columns (e.g. detected_anomalies.model_output) are returned as
    already-parsed Python objects (dict/list).

    Example:
        run_query("SELECT * FROM detected_anomalies WHERE anomaly_id = %s", (anomaly_id,))
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]


def list_tables() -> list[str]:
    rows = run_query(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name;"
    )
    return [r["table_name"] for r in rows]


def describe_table(table_name: str) -> list[dict[str, Any]]:
    return run_query(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position;",
        (table_name,),
    )


if __name__ == "__main__":
    print("Tables:", list_tables())
    for t in list_tables():
        print(f"\n{t}:")
        for col in describe_table(t):
            print(" ", col)
