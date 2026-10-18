import json
import time
from contextlib import closing
from pathlib import Path

from jarvis import db

# Imported, not copied, so the two cannot drift; brain never imports history, so no cycle.
from jarvis.brain import MAX_TURNS


class History:
    """The conversation turns saved between runs, newest 100 kept."""

    def __init__(
        self,
        path: str | Path,
        max_age_s: float = 12 * 3600,
        keep: int = 100,
        clock=time.time,
    ):
        self.path = path
        # A turn from yesterday carries stale tool results ("volume 40%", "playing ...")
        # and an old language can pull the reply into the wrong language.
        self.max_age_s = max_age_s
        self.keep = keep
        self.clock = clock

    def load(self, limit: int = MAX_TURNS) -> list[list[dict]]:
        """The newest `limit` turns that are not too old, oldest first."""
        with closing(db.connect(self.path)) as conn, conn:
            rows = conn.execute(
                "SELECT messages FROM turns WHERE ts >= ? ORDER BY id DESC LIMIT ?",
                (self.clock() - self.max_age_s, limit),
            ).fetchall()
        turns = []
        for (messages,) in reversed(rows):
            try:
                turns.append(json.loads(messages))
            except json.JSONDecodeError:
                continue  # one damaged row must not stop Jarvis starting
        return turns

    def clear(self) -> int:
        """Delete every saved turn; returns how many there were."""
        with closing(db.connect(self.path)) as conn, conn:
            return conn.execute("DELETE FROM turns").rowcount

    def save(self, turn: list[dict]) -> None:
        with closing(db.connect(self.path)) as conn, conn:
            conn.execute(
                "INSERT INTO turns (ts, messages) VALUES (?, ?)",
                (self.clock(), json.dumps(turn, ensure_ascii=False)),
            )
            conn.execute(
                "DELETE FROM turns WHERE id NOT IN "
                "(SELECT id FROM turns ORDER BY id DESC LIMIT ?)",
                (self.keep,),
            )
