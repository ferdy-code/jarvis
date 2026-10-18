import os
import sqlite3
import subprocess
import sys
from contextlib import closing

import pytest

from jarvis import db


def _user_version(path):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


def test_connect_creates_the_schema_at_version_1(tmp_path):
    path = tmp_path / "jarvis.sqlite3"
    with closing(db.connect(path)) as conn:
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert tables == {"turns", "facts"}
    assert _user_version(path) == 1


def test_connect_creates_the_parent_folder(tmp_path):
    path = tmp_path / "data" / "deeper" / "jarvis.sqlite3"
    db.connect(path).close()
    assert path.exists()


def test_reopening_keeps_rows_and_does_not_recreate_tables(tmp_path):
    path = tmp_path / "jarvis.sqlite3"
    with closing(db.connect(path)) as conn, conn:
        conn.execute(
            "INSERT INTO facts (ts, text, key) VALUES (1.0, 'Aku suka kopi', 'aku suka kopi')"
        )
    with closing(db.connect(path)) as conn:
        rows = conn.execute("SELECT text FROM facts").fetchall()
    assert rows == [("Aku suka kopi",)]
    assert _user_version(path) == 1


def test_a_newer_database_is_refused_and_left_alone(tmp_path):
    path = tmp_path / "jarvis.sqlite3"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA user_version = 2")
    with pytest.raises(RuntimeError, match="version 2"):
        db.connect(path)
    assert _user_version(path) == 2
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("SELECT count(*) FROM sqlite_master").fetchone()[0] == 0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "data/jarvis.sqlite3"),
        ("off", "None"),
        ("OFF ", "None"),
        ("", "None"),
        ("x/y.db", "x/y.db"),
    ],
)
def test_config_db_file(value, expected):
    # A fresh interpreter, because config reads the environment when it is imported.
    env = {k: v for k, v in os.environ.items() if k != "JARVIS_DB_FILE"}
    if value is not None:
        env["JARVIS_DB_FILE"] = value
    out = subprocess.run(
        [sys.executable, "-c", "from jarvis import config; print(config.DB_FILE)"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == expected
