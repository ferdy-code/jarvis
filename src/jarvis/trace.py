"""A trace of each turn: one JSON line saying where the time went and which tools ran.

A turn starts at the wake word (voice) or when a line is typed, and ends when the
reply has been spoken. Everything timed inside it is a span: recording, transcribing,
each model call, each tool, speaking. Code that is not inside a turn (unit tests, the
scripts) can still open spans; they are simply dropped.

Tracing must never break Jarvis, so a trace that cannot be written only prints a note.
"""

import json
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

PREVIEW_CHARS = 200

_current: ContextVar[Turn | None] = ContextVar("jarvis_turn", default=None)
_write_lock = threading.Lock()  # the typed and voice threads can both finish a turn


class Turn:
    """What is known about the turn in progress."""

    def __init__(self, source: str, fields: dict) -> None:
        self.started = time.perf_counter()
        self.record: dict = {
            "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
            "source": source,
            **fields,
        }
        self.spans: list[dict] = []

    def set(self, **fields) -> None:
        self.record.update(fields)


class Span:
    """Extra facts about one timed step, added with `set` while it runs."""

    def __init__(self, name: str, fields: dict) -> None:
        self.fields: dict = {"name": name, **fields}

    def set(self, **fields) -> None:
        self.fields.update(fields)


def preview(text: str) -> str:
    """The start of a long text, so one web page cannot fill the log."""
    text = " ".join(text.split())
    if len(text) <= PREVIEW_CHARS:
        return text
    return text[:PREVIEW_CHARS] + "…"


@contextmanager
def turn(path: str | Path | None, source: str, **fields) -> Iterator[Turn]:
    """Trace one turn and append it to `path` when it ends; no path means no file.

    A turn opened inside another one joins it: the voice loop opens the turn at the
    wake word, and `reply_to` opens one again without knowing whether it is already
    inside one.
    """
    outer = _current.get()
    if outer is not None:
        outer.set(**fields)
        yield outer
        return
    current = Turn(source, fields)
    token = _current.set(current)
    try:
        yield current
    except BaseException as error:
        current.set(error=type(error).__name__)
        raise
    finally:
        _current.reset(token)
        current.record["total_ms"] = _since(current.started)
        current.record["spans"] = current.spans
        if path is not None:
            _append(Path(path), current.record)


@contextmanager
def span(name: str, **fields) -> Iterator[Span]:
    """Time the block; it is recorded in the current turn, if there is one."""
    current = _current.get()
    entry = Span(name, fields)
    start = time.perf_counter()
    try:
        yield entry
    except BaseException as error:
        entry.set(error=type(error).__name__)
        raise
    finally:
        if current is not None:
            entry.fields["at_ms"] = round((start - current.started) * 1000)
            entry.fields["ms"] = _since(start)
            current.spans.append(entry.fields)


def _since(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def _append(path: Path, record: dict) -> None:
    try:
        line = json.dumps(record, ensure_ascii=False, default=str)
        with _write_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as file:
                file.write(line + "\n")
    except (OSError, ValueError) as error:
        print(f"(trace not written: {error})")
