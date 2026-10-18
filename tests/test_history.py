import sqlite3
from contextlib import closing

from jarvis import db
from jarvis.brain import MAX_TURNS
from jarvis.history import History


def make(tmp_path, now=1_000_000.0, **kwargs):
    return History(tmp_path / "h.sqlite3", clock=lambda: now, **kwargs)


def turn(n):
    return [
        {"role": "user", "content": f"q{n}"},
        {"role": "assistant", "content": f"a{n}"},
    ]


def test_a_turn_round_trips_with_indonesian_text_and_tool_calls(tmp_path):
    saved = [
        {"role": "user", "content": "Berapa baterai saya? Äpfel 日本"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "get_battery", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "80%"},
        {"role": "assistant", "content": "Baterai Anda 80 persen."},
    ]
    history = make(tmp_path)

    history.save(saved)

    assert history.load() == [saved]


def test_load_returns_the_newest_turns_oldest_first(tmp_path):
    history = make(tmp_path)
    for n in range(5):
        history.save(turn(n))

    assert history.load(limit=3) == [turn(2), turn(3), turn(4)]


def test_the_default_limit_is_the_brains_memory_size(tmp_path):
    history = make(tmp_path)
    for n in range(MAX_TURNS + 3):
        history.save(turn(n))

    assert history.load() == [turn(n) for n in range(3, MAX_TURNS + 3)]


def test_turns_older_than_12_hours_are_not_loaded(tmp_path):
    now = 1_000_000.0
    path = tmp_path / "h.sqlite3"
    History(path, clock=lambda: now - 12 * 3600 - 1).save(turn(0))
    History(path, clock=lambda: now - 12 * 3600 + 1).save(turn(1))

    assert History(path, clock=lambda: now).load() == [turn(1)]


def test_only_the_newest_keep_turns_stay_in_the_database(tmp_path):
    history = make(tmp_path, keep=3)
    for n in range(5):
        history.save(turn(n))

    assert history.load(limit=10) == [turn(2), turn(3), turn(4)]
    with closing(db.connect(history.path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0] == 3


def test_a_corrupt_row_is_skipped(tmp_path):
    history = make(tmp_path)
    history.save(turn(0))
    with closing(sqlite3.connect(history.path)) as conn, conn:
        conn.execute("INSERT INTO turns (ts, messages) VALUES (1000000.0, '{bad')")
    history.save(turn(1))

    assert history.load() == [turn(0), turn(1)]


def test_clear_removes_every_saved_turn(tmp_path):
    history = make(tmp_path)
    history.save(turn(1))
    history.save(turn(2))

    history.clear()

    assert history.load() == []
    with closing(db.connect(history.path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM turns").fetchone() == (0,)


def test_clear_deletes_every_turn_and_counts_them(tmp_path):
    history = make(tmp_path)
    history.save(turn(1))
    history.save(turn(2))

    assert history.clear() == 2
    assert history.load() == []
