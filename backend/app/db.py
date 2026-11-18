"""Small database layer for local SQLite and serverless PostgreSQL deployments."""
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from app.config import get_settings

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user','admin')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti TEXT PRIMARY KEY,
    expires_at INTEGER NOT NULL
);
"""

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user','admin')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti TEXT PRIMARY KEY,
    expires_at BIGINT NOT NULL
);
"""


class _PostgresCursor:
    def __init__(self, cursor: Any):
        self._cursor = cursor

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> Any:
        self._cursor.execute(query.replace("?", "%s"), params)
        return self

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> list[Any]:
        return self._cursor.fetchall()

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount


class _PostgresConnection:
    def __init__(self, connection: Any):
        self._connection = connection

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> _PostgresCursor:
        cursor = self._connection.cursor()
        return _PostgresCursor(cursor).execute(query, params)

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self.execute(statement)

@contextmanager
def get_conn() -> Iterator[Any]:
    settings = get_settings()
    if settings.database_url:
        import psycopg
        from psycopg.rows import dict_row

        connection = psycopg.connect(settings.database_url, row_factory=dict_row)
        try:
            yield _PostgresConnection(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return

    path = settings.database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as c:
        c.executescript(POSTGRES_SCHEMA if get_settings().database_url else SQLITE_SCHEMA)
