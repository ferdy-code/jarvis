import pytest

from jarvis import app
from jarvis.app import Assistant, is_yes, without_wake_phrase
from jarvis.facts import Facts
from jarvis.history import History


@pytest.mark.parametrize("answer", ["y", "yes", "Yes.", " ya ", "iya", "YES!", "Yeah."])
def test_clear_agreement_counts_as_yes(answer):
    assert is_yes(answer)


@pytest.mark.parametrize("answer", ["", "n", "no", "tidak", "yes but wait", "maybe"])
def test_anything_else_counts_as_no(answer):
    assert not is_yes(answer)


@pytest.mark.parametrize(
    ("heard", "command"),
    [
        ("Hey Jarvis, what time is it?", "what time is it?"),
        ("Hey Jarvis. Restart the PC.", "Restart the PC."),
        ("Hey, Jarvis. jam berapa sekarang", "jam berapa sekarang"),
        ("Okay Jarvis mute", "mute"),
        ("Jervis, kecilkan volume", "kecilkan volume"),
        ("Hey Jarvis. Hey Jarvis.", ""),
        ("Jarvis", ""),
        ("what time is it?", "what time is it?"),
        ("tell Jarvis I said hi", "tell Jarvis I said hi"),
    ],
)
def test_the_wake_phrase_is_removed_from_the_start_of_a_command(heard, command):
    assert without_wake_phrase(heard) == command


class FakeBrain:
    """Answers 'ok'. If `danger` is set, asks for confirmation first."""

    def __init__(self, confirm, danger=None):
        self.confirm = confirm
        self.danger = danger
        self.asked = []
        self.confirmed = None

    def ask(self, text, lang=None):
        self.asked.append(text)
        if self.danger:
            self.confirmed = self.confirm(self.danger)
        return "ok"


class FakeMic:
    """An open microphone: records when it was opened and closed."""

    def __init__(self, events):
        self.events = events

    def __enter__(self):
        self.events.append("mic open")
        return self

    def __exit__(self, *_):
        self.events.append("mic close")


class Room:
    """Stand-ins for the microphone, speakers and keyboard, recording what happened."""

    def __init__(self, heard=("what time is it", "en"), danger=None):
        self.events = []
        self.heard = list(heard) if isinstance(heard, list) else [heard]
        self.spoken = []
        self.mic = FakeMic(self.events)
        self.mics_used = []  # the microphone each step was given
        self.after_wake = []  # whether each listen came straight after the wake word
        self.terminal_answer = "n"
        self.assistant = Assistant(
            make_brain=lambda confirm: FakeBrain(confirm, danger),
            speak=self.speak,
            listen=self.listen,
            wait_for_wake=self.wait_for_wake,
            chime=self.chime,
            ask_terminal=self.ask_terminal,
            open_mic=lambda: self.mic,
        )
        self.brain = self.assistant.brain

    def wait_for_wake(self, mic=None):
        self.events.append("wake")
        self.mics_used.append(("wake", mic))

    def speak(self, text, lang=None):
        self.events.append("speak")
        self.spoken.append((text, lang))

    def chime(self, wait=False):
        self.events.append("chime-wait" if wait else "chime")

    def listen(self, mic=None, after_wake=False):
        self.events.append("listen")
        self.mics_used.append(("listen", mic))
        self.after_wake.append(after_wake)
        return self.heard.pop(0) if self.heard else ("", "en")

    def ask_terminal(self, question):
        self.events.append("terminal")
        return is_yes(self.terminal_answer)


def test_a_typed_turn_prints_and_speaks_the_reply(capsys):
    room = Room()

    room.assistant.reply_to("hello", "typed")

    assert "jarvis> ok" in capsys.readouterr().out
    assert room.spoken == [("ok", None)]


def test_a_voice_turn_goes_wake_chime_listen_then_answers_with_the_mic_closed(capsys):
    room = Room(heard=("what time is it", "en"))

    room.assistant.voice_once()

    assert room.events == [
        "mic open",
        "wake",
        "chime",
        "listen",
        "mic close",
        "speak",
    ]
    assert room.brain.asked == ["what time is it"]
    assert "what time is it" in capsys.readouterr().out


def test_the_same_open_microphone_serves_the_wake_word_and_the_command():
    room = Room()

    room.assistant.voice_once()

    assert room.mics_used == [("wake", room.mic), ("listen", room.mic)]


def test_the_command_is_recorded_as_coming_straight_after_the_wake_word():
    room = Room(
        heard=[("restart the pc", "en"), ("yes", "en")], danger="power(action=restart)"
    )

    room.assistant.voice_once()

    assert room.after_wake == [True, False]  # the command, then the spoken answer


def test_the_user_is_told_when_the_wake_word_was_heard(capsys):
    room = Room()

    room.assistant.voice_once()

    assert "wake word heard" in capsys.readouterr().out


def test_the_wake_phrase_is_not_sent_to_the_brain():
    room = Room(heard=("Hey Jarvis. Restart the PC.", "en"))

    room.assistant.voice_once()

    assert room.brain.asked == ["Restart the PC."]


def test_hearing_only_the_wake_phrase_counts_as_nothing_heard(capsys):
    room = Room(heard=("Hey Jarvis. Hey Jarvis.", "en"))

    room.assistant.voice_once()

    assert room.brain.asked == []
    assert "heard nothing" in capsys.readouterr().out


def test_nothing_heard_means_the_brain_is_not_asked(capsys):
    room = Room(heard=("", "en"))

    room.assistant.voice_once()

    assert room.brain.asked == []
    assert "heard nothing" in capsys.readouterr().out


def test_a_wake_word_during_a_spoken_reply_is_ignored():
    room = Room()

    with room.assistant.lock:  # Jarvis is busy talking
        room.assistant.voice_once()

    assert room.events == ["mic open", "wake", "mic close"]
    assert room.brain.asked == []


def test_a_typed_dangerous_action_asks_in_the_terminal():
    room = Room(danger="power(action=shutdown)")
    room.terminal_answer = "y"

    room.assistant.reply_to("shut down", "typed")

    assert room.brain.confirmed is True
    assert "terminal" in room.events
    assert "listen" not in room.events


@pytest.mark.parametrize(
    ("answer", "allowed"),
    [("ya", True), ("yes", True), ("tidak", False), ("no", False), ("", False)],
)
def test_a_spoken_dangerous_action_asks_aloud_and_listens(answer, allowed):
    room = Room(
        heard=[("restart the pc", "en"), (answer, "en")], danger="power(action=restart)"
    )

    room.assistant.voice_once()

    assert room.brain.confirmed is allowed
    question = room.spoken[0][0]
    assert "power action restart" in question
    assert "yes or no" in question
    assert "terminal" not in room.events


def test_the_spoken_question_is_followed_by_a_chime_and_shown_with_the_answer(capsys):
    room = Room(
        heard=[("restart the pc", "en"), ("yes", "en")], danger="power(action=restart)"
    )

    room.assistant.voice_once()

    events = room.events
    question_at = events.index("speak")
    # the chime is played to the end before the microphone opens
    assert events[question_at : question_at + 3] == ["speak", "chime-wait", "listen"]
    out = capsys.readouterr().out
    assert "power action restart" in out
    assert "you (voice)> yes" in out


def test_a_silent_answer_to_the_question_is_shown_as_nothing_heard(capsys):
    room = Room(
        heard=[("restart the pc", "en"), ("", "en")], danger="power(action=restart)"
    )

    room.assistant.voice_once()

    assert room.brain.confirmed is False
    assert "you (voice)> (heard nothing)" in capsys.readouterr().out


def test_the_spoken_question_is_in_the_language_the_user_spoke():
    room = Room(
        heard=[("restart komputer", "id"), ("tidak", "id")],
        danger="power(action=restart)",
    )

    room.assistant.voice_once()

    question, lang = room.spoken[0]
    assert "ya atau tidak" in question
    assert lang == "id"


def test_after_a_voice_turn_a_typed_turn_asks_in_the_terminal():
    room = Room(heard=[("hello", "en")], danger="power(action=restart)")
    room.assistant.brain.danger = None
    room.assistant.voice_once()
    room.assistant.brain.danger = "power(action=restart)"

    room.assistant.reply_to("restart", "typed")

    assert "terminal" in room.events


def test_a_speaker_problem_turns_voice_off_but_the_chat_goes_on(capsys):
    room = Room()

    def broken(text, lang=None):
        raise RuntimeError("no audio device")

    room.assistant.speak = broken

    room.assistant.reply_to("one", "typed")
    room.assistant.reply_to("two", "typed")

    out = capsys.readouterr().out
    assert out.count("jarvis> ok") == 2
    assert "voice stopped" in out and "no audio device" in out
    assert room.assistant.speak is None


def test_voice_input_gives_up_after_three_failures_in_a_row(monkeypatch, capsys):
    monkeypatch.setattr(app.time, "sleep", lambda _s: None)
    room = Room()
    attempts = []

    def broken_wake(mic=None):
        attempts.append(1)
        raise OSError("microphone unplugged")

    room.assistant.wait_for_wake = broken_wake

    room.assistant.voice_loop()

    assert len(attempts) == 3
    out = capsys.readouterr().out
    assert "microphone unplugged" in out and "Voice input is off" in out


def test_a_success_resets_the_failure_count(monkeypatch):
    monkeypatch.setattr(app.time, "sleep", lambda _s: None)
    room = Room(heard=[("hi", "en")] * 10)
    outcomes = iter(["fail", "fail", "ok", "fail", "fail", "fail"])
    attempts = []

    def wake(mic=None):
        attempts.append(1)
        if next(outcomes) == "fail":
            raise OSError("glitch")

    room.assistant.wait_for_wake = wake

    room.assistant.voice_loop()

    assert len(attempts) == 6


def test_a_typed_turn_is_traced_with_its_text_and_reply(tmp_path):
    import json

    class EchoBrain:
        def ask(self, text, lang=None):
            return f"echo: {text}"

    path = tmp_path / "trace.jsonl"
    assistant = Assistant(make_brain=lambda confirm: EchoBrain(), trace_path=path)

    assistant.reply_to("hello", "typed")

    record = json.loads(path.read_text(encoding="utf-8"))
    assert (record["source"], record["text"], record["reply"]) == (
        "typed",
        "hello",
        "echo: hello",
    )


def test_without_a_trace_path_no_file_is_made(tmp_path, monkeypatch):
    class EchoBrain:
        def ask(self, text, lang=None):
            return text

    monkeypatch.chdir(tmp_path)
    assistant = Assistant(make_brain=lambda confirm: EchoBrain())

    assistant.reply_to("hello", "typed")

    assert list(tmp_path.iterdir()) == []


def test_a_voice_turn_is_traced_from_the_wake_word_to_the_reply(tmp_path):
    import json

    room = Room(heard=("Hey Jarvis, what time is it?", "en"))
    room.assistant.trace_path = tmp_path / "trace.jsonl"

    room.assistant.voice_once()

    [line] = room.assistant.trace_path.read_text(encoding="utf-8").splitlines()
    record = json.loads(line)
    assert record["source"] == "voice"
    assert record["heard"] == "Hey Jarvis, what time is it?"
    assert record["text"] == "what time is it?"
    assert record["lang"] == "en"
    assert record["reply"] == "ok"


def test_a_wake_word_that_led_to_nothing_is_still_traced(tmp_path):
    import json

    room = Room(heard=("", "en"))
    room.assistant.trace_path = tmp_path / "trace.jsonl"

    room.assistant.voice_once()

    [line] = room.assistant.trace_path.read_text(encoding="utf-8").splitlines()
    record = json.loads(line)
    assert record["source"] == "voice"
    assert record["heard"] == ""
    assert "reply" not in record


def test_a_spoken_confirmation_is_traced_with_its_answer(tmp_path):
    import json

    room = Room(
        heard=[("restart the pc", "en"), ("yes", "en")], danger="power(action=restart)"
    )
    room.assistant.trace_path = tmp_path / "trace.jsonl"

    room.assistant.voice_once()

    record = json.loads(room.assistant.trace_path.read_text(encoding="utf-8"))
    [confirm] = [span for span in record["spans"] if span["name"] == "confirm"]
    assert confirm["action"] == "power(action=restart)"
    assert confirm["answer"] is True


# --- main(): --reset-memory and the memory setting ------------------------------------


def _fail(*_args, **_kwargs):
    raise AssertionError("must not be called")


@pytest.fixture
def no_models(monkeypatch):
    """Anything that would load a client, a brain or an audio model fails the test."""
    monkeypatch.setattr(app.openai, "OpenAI", _fail)
    monkeypatch.setattr(app, "Brain", _fail)
    monkeypatch.setattr(app, "Assistant", _fail)
    monkeypatch.setattr(app, "load_speaker", _fail)
    monkeypatch.setattr(app, "load_microphone", _fail)
    for module in (app.stt, app.tts, app.wake):
        monkeypatch.setattr(module, "load", _fail)


def _seeded_database(tmp_path):
    path = tmp_path / "data" / "jarvis.sqlite3"
    facts, history = Facts(path), History(path)
    facts.add("my cat is called Mochi")
    facts.add("my sister lives in Bandung")
    history.save([{"role": "user", "content": "hi"}])
    return path, facts, history


def _run_main(monkeypatch, path, *argv, answer=None):
    monkeypatch.setattr(app.config, "DB_FILE", path)
    monkeypatch.setattr("sys.argv", ["jarvis", *argv])
    prompts = []

    def fake_input(prompt=""):
        prompts.append(prompt)
        if answer is None:
            raise EOFError
        return answer

    monkeypatch.setattr("builtins.input", fake_input)
    app.main()
    return prompts


def test_reset_memory_after_yes_empties_both_tables(
    no_models, monkeypatch, tmp_path, capsys
):
    path, facts, history = _seeded_database(tmp_path)

    prompts = _run_main(monkeypatch, path, "--reset-memory", answer="y")

    assert prompts == ["Delete all remembered facts and saved history? [y/N] "]
    assert facts.all() == []
    assert history.load() == []
    assert "Deleted 2 facts and 1 saved turns." in capsys.readouterr().out


@pytest.mark.parametrize("answer", ["n", "", "maybe", "yes but wait"])
def test_reset_memory_changes_nothing_without_a_clear_yes(
    no_models, monkeypatch, tmp_path, capsys, answer
):
    path, facts, history = _seeded_database(tmp_path)

    _run_main(monkeypatch, path, "--reset-memory", answer=answer)

    assert len(facts.all()) == 2
    assert len(history.load()) == 1
    assert "Nothing was deleted." in capsys.readouterr().out


def test_reset_memory_with_no_answer_available_changes_nothing(
    no_models, monkeypatch, tmp_path
):
    path, facts, _history = _seeded_database(tmp_path)

    _run_main(monkeypatch, path, "--reset-memory")  # input() raises EOFError

    assert len(facts.all()) == 2


def test_reset_memory_does_not_create_a_missing_file(
    no_models, monkeypatch, tmp_path, capsys
):
    path = tmp_path / "data" / "jarvis.sqlite3"

    prompts = _run_main(monkeypatch, path, "--reset-memory", answer="y")

    assert prompts == []  # nothing to ask about
    assert not path.exists()
    assert not path.parent.exists()
    assert "nothing to delete" in capsys.readouterr().out


def test_reset_memory_with_memory_off_creates_nothing(
    no_models, monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)

    prompts = _run_main(monkeypatch, None, "--reset-memory", answer="y")

    assert prompts == []
    assert list(tmp_path.iterdir()) == []
    assert "JARVIS_DB_FILE=off" in capsys.readouterr().out


class _StubClient:
    def __init__(self, *_args, **_kwargs):
        pass


def _brain_kwargs(monkeypatch, path):
    """The keyword arguments `main` gives the Brain in a typed-only run."""
    seen = {}

    def fake_brain(*_args, **kwargs):
        seen.update(kwargs)
        return FakeBrain(kwargs["confirm"])

    monkeypatch.setattr(app.openai, "OpenAI", _StubClient)
    monkeypatch.setattr(app, "Brain", fake_brain)
    _run_main(monkeypatch, path, "--no-voice")  # the typed loop ends at EOF
    return seen


def test_with_memory_off_main_offers_no_memory_and_creates_no_file(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)

    kwargs = _brain_kwargs(monkeypatch, None)

    assert "remember" not in kwargs["tools"]
    assert "forget" not in kwargs["tools"]
    assert kwargs["history"] is None
    assert kwargs["facts"] is None
    assert list(tmp_path.iterdir()) == []


def test_with_memory_on_main_offers_the_memory_tools_history_and_facts(
    monkeypatch, tmp_path
):
    kwargs = _brain_kwargs(monkeypatch, tmp_path / "jarvis.sqlite3")

    assert {"remember", "forget"} <= set(kwargs["tools"])
    assert isinstance(kwargs["history"], History)
    assert kwargs["facts"]() == []
