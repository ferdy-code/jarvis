import json
import time

import pytest

from jarvis import trace


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_a_turn_is_written_as_one_json_line(tmp_path):
    path = tmp_path / "trace.jsonl"

    with trace.turn(path, "typed", text="jam berapa?") as turn:
        turn.set(reply="Jam 18:03.")

    [record] = lines(path)
    assert record["source"] == "typed"
    assert record["text"] == "jam berapa?"
    assert record["reply"] == "Jam 18:03."
    assert record["total_ms"] >= 0
    assert record["spans"] == []
    assert "T" in record["ts"]  # an ISO timestamp


def test_turns_are_appended_not_overwritten(tmp_path):
    path = tmp_path / "trace.jsonl"

    for text in ("one", "two"):
        with trace.turn(path, "typed", text=text):
            pass

    assert [record["text"] for record in lines(path)] == ["one", "two"]


def test_the_folder_is_created_when_missing(tmp_path):
    path = tmp_path / "logs" / "trace.jsonl"

    with trace.turn(path, "typed"):
        pass

    assert path.exists()


def test_indonesian_text_is_written_as_is(tmp_path):
    path = tmp_path / "trace.jsonl"

    with trace.turn(path, "voice", text="putarkan lagu yang tenang"):
        pass

    assert "putarkan lagu yang tenang" in path.read_text(encoding="utf-8")


def test_no_path_means_nothing_is_written(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with trace.turn(None, "typed", text="hi"):
        pass

    assert list(tmp_path.iterdir()) == []


def test_a_span_records_its_name_fields_and_duration(tmp_path):
    path = tmp_path / "trace.jsonl"

    with trace.turn(path, "typed"), trace.span("llm", with_tools=True) as span:
        time.sleep(0.02)
        span.set(tool_calls=["get_datetime"])

    [record] = lines(path)
    [span] = record["spans"]
    assert span["name"] == "llm"
    assert span["with_tools"] is True
    assert span["tool_calls"] == ["get_datetime"]
    assert span["ms"] >= 20


def test_spans_say_when_they_started_inside_the_turn(tmp_path):
    path = tmp_path / "trace.jsonl"

    with trace.turn(path, "typed"):
        with trace.span("first"):
            pass
        time.sleep(0.03)
        with trace.span("second"):
            pass

    first, second = lines(path)[0]["spans"]
    assert first["at_ms"] < 30 <= second["at_ms"]


def test_a_failing_span_is_recorded_and_the_error_still_surfaces(tmp_path):
    path = tmp_path / "trace.jsonl"

    with (
        pytest.raises(ZeroDivisionError),
        trace.turn(path, "typed"),
        trace.span("tool"),
    ):
        1 / 0  # noqa: B018

    [record] = lines(path)
    assert record["spans"][0]["error"] == "ZeroDivisionError"
    assert record["error"] == "ZeroDivisionError"


def test_a_span_outside_a_turn_is_harmless():
    with trace.span("llm") as span:
        span.set(anything="goes")


def test_a_turn_opened_inside_a_turn_joins_it(tmp_path):
    path = tmp_path / "trace.jsonl"

    with (
        trace.turn(path, "voice") as outer,
        trace.turn(path, "voice", text="hello") as inner,
        trace.span("llm"),
    ):
        assert inner is outer

    [record] = lines(path)  # written once, when the outer turn ended
    assert record["text"] == "hello"
    assert [span["name"] for span in record["spans"]] == ["llm"]


def test_a_new_turn_starts_clean_after_the_last_one(tmp_path):
    path = tmp_path / "trace.jsonl"
    with trace.turn(path, "typed", text="one"), trace.span("llm"):
        pass

    with trace.turn(path, "typed", text="two"):
        pass

    assert lines(path)[1]["spans"] == []


def test_a_trace_that_cannot_be_written_does_not_stop_the_turn(tmp_path, capsys):
    blocked = tmp_path / "taken"
    blocked.mkdir()  # a folder where the file should go

    with trace.turn(blocked, "typed", text="hi") as turn:
        turn.set(reply="still answered")

    assert "trace not written" in capsys.readouterr().out


def test_preview_cuts_long_text_and_flattens_whitespace():
    assert trace.preview("a\n  b") == "a b"
    long = trace.preview("x" * 500)
    assert len(long) == trace.PREVIEW_CHARS + 1
    assert long.endswith("…")
