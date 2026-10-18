import re
import time
from contextlib import closing
from pathlib import Path

from jarvis import db

MAX_FACTS = 30
MIN_LENGTH, MAX_LENGTH = 3, 200
SECRET_MESSAGE = "I do not store passwords, keys or card or ID numbers"

_SECRET_WORDS = re.compile(
    r"(?<!\w)(?:password|passwd|kata\s+sandi|pin|otp|token|api\s+key|secret|cvv)(?!\w)",
    re.IGNORECASE,
)
_LONG_NUMBER = re.compile(r"\d{9,}")


def looks_secret(text: str) -> bool:
    """A password-like word, or a number long enough to be a card or ID number."""
    return bool(
        _SECRET_WORDS.search(text) or _LONG_NUMBER.search(re.sub(r"[ -]", "", text))
    )


def _normalise(text: str) -> str:
    return " ".join(text.split())


class Facts:
    """Short things the user asked Jarvis to remember, at most 30."""

    def __init__(self, path: str | Path):
        self.path = path

    def all(self) -> list[str]:
        with closing(db.connect(self.path)) as conn, conn:
            rows = conn.execute("SELECT text FROM facts ORDER BY id").fetchall()
        return [text for (text,) in rows]

    def add(self, text: str) -> str:
        text = _normalise(text)
        if not MIN_LENGTH <= len(text) <= MAX_LENGTH:
            raise ValueError(
                f"a fact must be between {MIN_LENGTH} and {MAX_LENGTH} characters"
            )
        if looks_secret(text):
            raise ValueError(SECRET_MESSAGE)
        key = text.casefold()
        with closing(db.connect(self.path)) as conn, conn:
            if conn.execute("SELECT 1 FROM facts WHERE key = ?", (key,)).fetchone():
                return "duplicate"
            if conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0] >= MAX_FACTS:
                raise ValueError(
                    f"memory is full ({MAX_FACTS} facts); ask the user which one to forget"
                )
            conn.execute(
                "INSERT INTO facts (ts, text, key) VALUES (?, ?, ?)",
                (time.time(), text, key),
            )
        return "added"

    def remove(self, query: str) -> list[str]:
        """Remove every fact containing the query; returns what was removed."""
        key = _normalise(query).casefold()
        if len(key) < MIN_LENGTH:
            raise ValueError(f"say at least {MIN_LENGTH} letters of the fact to forget")
        with closing(db.connect(self.path)) as conn, conn:
            rows = conn.execute(
                "SELECT id, text FROM facts WHERE instr(key, ?) > 0 ORDER BY id", (key,)
            ).fetchall()
            conn.executemany(
                "DELETE FROM facts WHERE id = ?", [(id_,) for id_, _ in rows]
            )
        return [text for _, text in rows]
