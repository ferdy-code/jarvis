from types import SimpleNamespace

import numpy as np

from jarvis import stt


def silence():
    return np.zeros(stt.BLOCK, dtype=np.float32)


def speech():
    return np.full(stt.BLOCK, 0.2, dtype=np.float32)


def reader(*blocks, then=silence):
    """A fake microphone: the given blocks, then `then()` forever."""
    queue = iter(blocks)

    def read():
        block = next(queue, None)
        return then() if block is None else block

    return read


def test_nobody_speaking_gives_up_with_no_audio():
    assert stt._record(reader()) is None


def test_recording_stops_after_a_second_of_silence_following_speech():
    mic = reader(*[silence()] * 5, *[speech()] * 10)

    audio = stt._record(mic)

    loud = np.abs(audio) > 0.1
    assert loud.sum() == 10 * stt.BLOCK
    trailing = len(audio) - np.flatnonzero(loud)[-1] - 1
    assert 1.0 <= trailing / stt.SAMPLE_RATE < 1.2


def test_a_little_quiet_audio_before_the_speech_is_kept():
    mic = reader(*[silence()] * 8, *[speech()] * 4)

    audio = stt._record(mic)

    first_loud = np.flatnonzero(np.abs(audio) > 0.1)[0]
    assert first_loud == stt.PREROLL_BLOCKS * stt.BLOCK


def test_recording_is_cut_off_after_the_maximum_length():
    audio = stt._record(reader(then=speech))

    seconds = len(audio) / stt.SAMPLE_RATE
    assert stt.MAX_RECORD_S - 0.1 < seconds <= stt.MAX_RECORD_S


def test_speech_that_starts_late_is_still_heard():
    wait_blocks = int(stt.MAX_WAIT_S * stt.SAMPLE_RATE / stt.BLOCK)
    mic = reader(*[silence()] * (wait_blocks - 2), *[speech()] * 3)

    assert stt._record(mic) is not None


class FakeWhisper:
    """Returns scripted (segments, info) pairs and records how it was called."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def transcribe(self, audio, **kwargs):
        self.calls.append(kwargs)
        return self.results.pop(0)


def result(words, detected, probs=None):
    segments = [SimpleNamespace(text=f" {w} ") for w in words]
    info = SimpleNamespace(
        language=detected, all_language_probs=list((probs or {detected: 1.0}).items())
    )
    return iter(segments), info


def test_text_and_language_are_returned_when_it_is_english_or_indonesian():
    model = FakeWhisper(result(["What", "time", "is", "it?"], "en"))

    assert stt.transcribe(model, np.zeros(10)) == ("What time is it?", "en")
    assert len(model.calls) == 1


def test_another_language_is_replaced_by_the_likelier_of_english_or_indonesian():
    probs = {"es": 0.5, "id": 0.3, "en": 0.1}
    model = FakeWhisper(
        result(["Restar", "computer"], "es", probs),
        result(["Restart", "komputer"], "id"),
    )

    text, lang = stt.transcribe(model, np.zeros(10))

    assert (text, lang) == ("Restart komputer", "id")
    assert model.calls[1]["language"] == "id"


def test_english_is_chosen_over_indonesian_when_it_is_likelier():
    probs = {"cs": 0.6, "en": 0.3, "id": 0.1}
    model = FakeWhisper(result(["x"], "cs", probs), result(["Yes."], "en"))

    assert stt.transcribe(model, np.zeros(10)) == ("Yes.", "en")
    assert model.calls[1]["language"] == "en"


def test_no_speech_gives_empty_text():
    model = FakeWhisper(result([], "en"))

    assert stt.transcribe(model, np.zeros(10)) == ("", "en")


def test_whisper_is_told_to_filter_non_speech_and_given_the_command_vocabulary():
    model = FakeWhisper(result(["Hi"], "en"))

    stt.transcribe(model, np.zeros(10))

    assert model.calls[0]["vad_filter"] is True
    assert "volume" in model.calls[0]["initial_prompt"]
