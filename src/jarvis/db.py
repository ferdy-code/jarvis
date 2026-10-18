import sqlite3
from pathlib import Path

VERSION = 1

_SCHEMA = f"""
BEGIN;
CREATE TABLE turns (id INTEGER PRIMARY KEY, ts REAL NOT NULL, messages TEXT NOT NULL);
CREATE TABLE facts (
    id INTEGER PRIMARY KEY, ts REAL NOT NULL, text TEXT NOT NULL, key TEXT NOT NULL UNIQUE
);
PRAGMA user_version = {VERSION};
COMMIT;
"""


def connect(path: str | Path) -> sqlite3.Connection:
    """Open the memory database, creating it on first use.

    Callers open one connection per operation (`with closing(connect(path)), conn:`)
    because the typed thread and the voice thread can both write.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version == 0:
        conn.executescript(_SCHEMA)
    elif version > VERSION:
        conn.close()
        raise RuntimeError(
            f"{path} is database version {version}, but this Jarvis only reads version {VERSION}"
        )
    return conn
