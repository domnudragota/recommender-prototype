import os
import sqlite3
from typing import Iterator, Optional
from backend.app.config import settings
from backend.app.schema import SCHEMA_SQL

def _sqlite_path_from_url(database_url: str) -> str:
    # this should support:
    #   sqlite:///./data/app.db  -> ./data/app.db
    #   sqlite:////abs/path.db   -> /abs/path.db
    if not database_url.startswith("sqlite:"):
        raise ValueError("Only sqlite DATABASE_URL is supported")

    if database_url.startswith("sqlite:///./") or database_url.startswith("sqlite:///../"):
        return database_url.replace("sqlite:///", "", 1)

    if database_url.startswith("sqlite:////"):
        # absolute path
        return database_url.replace("sqlite:////", "/", 1)

    if database_url.startswith("sqlite:///"):
        # treat as absolute (/path...)
        return database_url.replace("sqlite://", "", 1)

    # last resort, hopefully we don't get there
    return database_url.replace("sqlite:", "", 1)

def get_db_path() -> str:
    return _sqlite_path_from_url(settings.database_url)

def connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()
