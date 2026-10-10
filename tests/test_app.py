import pytest

from jarvis import app
from jarvis.app import Assistant, is_yes


@pytest.mark.parametrize("answer", ["y", "yes", "Yes.", " ya ", "iya", "YES!", "Yeah."])
def test_clear_agreement_counts_as_yes(answer):
    assert is_yes(answer)


@pytest.mark.parametrize("answer", ["", "n", "no", "tidak", "yes but wait", "maybe"])
def test_anything_else_counts_as_no(answer):
    assert not is_yes(answer)


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


class Room:
    """Stand-ins for the microphone, speakers and keyboard, recording what happened."""

    def __init__(self, heard=("what time is it", "en"), danger=None):
        self.events = []
        self.heard = list(heard) if isinstance(heard, list) else [heard]
        self.spoken = []
        self.terminal_answer = "n"
        self.assistant = Assistant(
            make_brain=lambda confirm: FakeBrain(confirm, danger),
            speak=self.speak,
            listen=self.listen,
            wait_for_wake=lambda: self.events.append("wake"),
            chime=lambda: self.events.append("chime"),
            ask_terminal=self.ask_terminal,
        )
        self.brain = self.assistant.brain

    def speak(self, text, lang=None):
        self.events.append("speak")
        self.spoken.append((text, lang))

    def listen(self):
        self.events.append("listen")
        return self.heard.pop(0) if self.heard else ("", "en")

    def ask_terminal(self, question):
        self.events.append("terminal")
        return is_yes(self.terminal_answer)


def test_a_typed_turn_prints_and_speaks_the_reply(capsys):
    room = Room()

    room.assistant.reply_to("hello", "typed")

    assert "jarvis> ok" in capsys.readouterr().out
    assert room.spoken == [("ok", None)]


def test_a_voice_turn_goes_wake_chime_listen_answer_speak(capsys):
    room = Room(heard=("what time is it", "en"))

    room.assistant.voice_once()

    assert room.events == ["wake", "chime", "listen", "speak"]
    assert room.brain.asked == ["what time is it"]
    assert "what time is it" in capsys.readouterr().out


def test_nothing_heard_means_the_brain_is_not_asked(capsys):
    room = Room(heard=("", "en"))

    room.assistant.voice_once()

    assert room.brain.asked == []
    assert "heard nothing" in capsys.readouterr().out


def test_a_wake_word_during_a_spoken_reply_is_ignored():
    room = Room()

    with room.assistant.lock:  # Jarvis is busy talking
        room.assistant.voice_once()

    assert room.events == ["wake"]
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

    def broken_wake():
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

    def wake():
        attempts.append(1)
        if next(outcomes) == "fail":
            raise OSError("glitch")

    room.assistant.wait_for_wake = wake

    room.assistant.voice_loop()

    assert len(attempts) == 6
