"""Database query and schema inspection tools."""

from __future__ import annotations

import json
import re
from typing import Any

_SELECT_ONLY_RE = re.compile(r"^\s*SELECT\s", re.IGNORECASE)


def _check_select_only(sql: str) -> str | None:
    """Return an error string if the SQL is not SELECT-only."""
    stripped = sql.strip().lstrip("(")
    upper = stripped.upper()
    disallowed = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "EXEC", "EXECUTE")
    for keyword in disallowed:
        if upper.startswith(keyword):
            return f"Only SELECT queries are allowed. Got: {keyword}"
    if not _SELECT_ONLY_RE.match(sql):
        return "Only SELECT queries are allowed."
    return None


def _parse_conn_str(conn_str: str, db_type: str) -> dict[str, Any]:
    """Parse a connection string into a dictionary of params."""
    if db_type == "sqlite":
        return {"database": conn_str}
    # postgresql / mysql: dialect://user:pass@host:port/dbname
    pattern = r"^(?P<dialect>\w+)://(?:(?P<user>[^:]+)(?::(?P<pass>[^@]*))?@)?(?P<host>[^:/]+)(?::(?P<port>\d+))?/(?P<db>.+)$"
    m = re.match(pattern, conn_str)
    if not m:
        raise ValueError(f"Could not parse connection string for {db_type}")
    return {
        "host": m.group("host"),
        "port": int(m.group("port")) if m.group("port") else None,
        "user": m.group("user"),
        "password": m.group("pass") or "",
        "database": m.group("db"),
        "dialect": m.group("dialect"),
    }


class DatabaseTools:
    """Tools for querying databases and inspecting schemas."""

    @staticmethod
    def query_schema() -> dict[str, Any]:
        return {
            "description": "Execute a SELECT-only SQL query against a database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SELECT SQL query"},
                    "db_type": {
                        "type": "string",
                        "enum": ["sqlite", "postgresql", "mysql"],
                        "description": "Database type",
                    },
                    "conn_str": {
                        "type": "string",
                        "description": "Connection string: file path for SQLite, or URL for PG/MySQL",
                    },
                    "params": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional query parameters",
                    },
                },
                "required": ["sql", "db_type", "conn_str"],
            },
        }

    @staticmethod
    def schema_schema() -> dict[str, Any]:
        return {
            "description": "Retrieve the schema (table structures) of a database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "db_type": {
                        "type": "string",
                        "enum": ["sqlite", "postgresql", "mysql"],
                    },
                    "conn_str": {"type": "string", "description": "Connection string"},
                },
                "required": ["db_type", "conn_str"],
            },
        }

    @staticmethod
    def explain_schema() -> dict[str, Any]:
        return {
            "description": "Show the query execution plan for a SQL statement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SQL statement to explain"},
                    "db_type": {
                        "type": "string",
                        "enum": ["sqlite", "postgresql", "mysql"],
                    },
                    "conn_str": {"type": "string", "description": "Connection string"},
                },
                "required": ["sql", "db_type", "conn_str"],
            },
        }

    @staticmethod
    def list_tables_schema() -> dict[str, Any]:
        return {
            "description": "List all tables in the database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conn_str": {"type": "string", "description": "Connection string"},
                    "db_type": {
                        "type": "string",
                        "enum": ["sqlite", "postgresql", "mysql"],
                        "default": "sqlite",
                    },
                },
                "required": ["conn_str"],
            },
        }

    async def query(
        self,
        sql: str,
        db_type: str,
        conn_str: str,
        params: list[str] | None = None,
    ) -> str:
        err = _check_select_only(sql)
        if err:
            return json.dumps({"error": err})

        try:
            if db_type == "sqlite":
                import sqlite3

                conn = sqlite3.connect(conn_str)
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(sql, params or [])
                rows = [dict(row) for row in cursor.fetchall()]
                conn.close()
                return json.dumps({"rows": rows, "count": len(rows)})

            if db_type == "postgresql":
                try:
                    import psycopg2
                    import psycopg2.extras
                except ImportError:
                    return json.dumps({"error": "psycopg2 is required for PostgreSQL"})
                params_dict = _parse_conn_str(conn_str, db_type)
                conn = psycopg2.connect(**params_dict)
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute(sql, params or [])
                rows = [dict(row) for row in cursor.fetchall()]
                conn.close()
                return json.dumps({"rows": rows, "count": len(rows)})

            if db_type == "mysql":
                try:
                    import pymysql
                except ImportError:
                    return json.dumps({"error": "pymysql is required for MySQL"})
                params_dict = _parse_conn_str(conn_str, db_type)
                conn = pymysql.connect(**params_dict)
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                cursor.execute(sql, params or [])
                rows = list(cursor.fetchall())
                conn.close()
                return json.dumps({"rows": rows, "count": len(rows)})

            return json.dumps({"error": f"Unsupported database type: {db_type}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def schema(self, db_type: str, conn_str: str) -> str:
        try:
            if db_type == "sqlite":
                import sqlite3

                conn = sqlite3.connect(conn_str)
                cursor = conn.execute(
                    "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = [{"name": row[0], "sql": row[1]} for row in cursor.fetchall()]
                conn.close()
                return json.dumps({"db_type": db_type, "tables": tables})

            if db_type == "postgresql":
                try:
                    import psycopg2
                    import psycopg2.extras
                except ImportError:
                    return json.dumps({"error": "psycopg2 is required"})
                params = _parse_conn_str(conn_str, db_type)
                conn = psycopg2.connect(**params)
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute(
                    "SELECT table_name, table_schema FROM information_schema.tables "
                    "WHERE table_schema NOT IN ('pg_catalog', 'information_schema') ORDER BY table_name"
                )
                tables = [dict(row) for row in cursor.fetchall()]
                conn.close()
                return json.dumps({"db_type": db_type, "tables": tables})

            if db_type == "mysql":
                try:
                    import pymysql
                except ImportError:
                    return json.dumps({"error": "pymysql is required"})
                params = _parse_conn_str(conn_str, db_type)
                conn = pymysql.connect(**params)
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                cursor.execute("SHOW TABLES")
                rows = list(cursor.fetchall())
                conn.close()
                return json.dumps({"db_type": db_type, "tables": [list(r.values())[0] for r in rows]})

            return json.dumps({"error": f"Unsupported database type: {db_type}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def explain(self, sql: str, db_type: str, conn_str: str) -> str:
        try:
            if db_type == "sqlite":
                import sqlite3

                conn = sqlite3.connect(conn_str)
                cursor = conn.execute(f"EXPLAIN QUERY PLAN {sql}")
                plan = [dict(row) for row in cursor.fetchall()]
                conn.close()
                return json.dumps({"plan": plan})

            if db_type == "postgresql":
                try:
                    import psycopg2
                    import psycopg2.extras
                except ImportError:
                    return json.dumps({"error": "psycopg2 is required"})
                params = _parse_conn_str(conn_str, db_type)
                conn = psycopg2.connect(**params)
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute(f"EXPLAIN (FORMAT JSON) {sql}")
                plan = cursor.fetchone()
                conn.close()
                return json.dumps({"plan": dict(plan) if plan else {}})

            if db_type == "mysql":
                try:
                    import pymysql
                except ImportError:
                    return json.dumps({"error": "pymysql is required"})
                params = _parse_conn_str(conn_str, db_type)
                conn = pymysql.connect(**params)
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                cursor.execute(f"EXPLAIN {sql}")
                plan = list(cursor.fetchall())
                conn.close()
                return json.dumps({"plan": plan})

            return json.dumps({"error": f"Unsupported database type: {db_type}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def list_tables(self, conn_str: str, db_type: str = "sqlite") -> str:
        """List all tables in the database."""
        return await self.schema(db_type, conn_str)
