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


def test_mic_peak_is_the_loudest_sample_after_the_device_warms_up(monkeypatch):
    levels = [0.9, 0.9, 0.9, 0.0, 0.3, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    class Stream:
        def __init__(self, **_settings):
            self.blocks = iter(levels)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self, frames):
            return np.full((frames, 1), next(self.blocks), dtype=np.float32), False

    monkeypatch.setattr("sounddevice.InputStream", Stream)

    assert stt.mic_peak(seconds=0.8) == np.float32(0.3)


class BlockStream:
    """A microphone that plays int16 blocks, then silence, and notes if it was closed."""

    def __init__(self, *blocks):
        self.blocks = iter(blocks)
        self.closed = False

    def read(self, frames):
        block = next(self.blocks, None)
        if block is None:
            block = np.zeros(frames, dtype=np.int16)
        return block.reshape(-1, 1), False

    def __exit__(self, *_):
        self.closed = True


def test_listen_records_from_the_given_stream_and_hands_float_audio_to_whisper(
    monkeypatch,
):
    heard = []

    class Whisper:
        def transcribe(self, audio, **_):
            heard.append(audio)
            return iter([SimpleNamespace(text=" yes ")]), SimpleNamespace(
                language="en", all_language_probs=[("en", 1.0)]
            )

    monkeypatch.setattr(stt, "_model", lambda: Whisper())
    loud = np.full(stt.BLOCK, 16384, dtype=np.int16)  # half of full scale
    stream = BlockStream(*[loud] * 5)

    assert stt.listen(stream) == ("yes", "en")

    audio = heard[0]
    assert audio.dtype == np.float32
    assert abs(float(audio.max()) - 0.5) < 0.01
    assert not stream.closed  # the caller owns the microphone


def test_listen_gives_up_when_nobody_speaks(monkeypatch):
    monkeypatch.setattr(stt, "_model", lambda: None)

    assert stt.listen(BlockStream()) == ("", "en")


def quiet_voice(level=0.007):
    return np.full(stt.BLOCK, level, dtype=np.float32)


def test_a_dip_below_the_threshold_does_not_end_the_recording(monkeypatch):
    monkeypatch.setattr(stt.config, "MIC_THRESHOLD", 0.01)
    # a quiet voice flickering between half the threshold and the threshold
    mic = reader(*[speech()] * 3, *[quiet_voice()] * 20, *[speech()] * 3)

    audio = stt._record(mic)

    assert (np.abs(audio) > 0.1).sum() == 6 * stt.BLOCK  # both bursts of speech


def test_real_silence_still_ends_the_recording(monkeypatch):
    monkeypatch.setattr(stt.config, "MIC_THRESHOLD", 0.01)
    mic = reader(*[speech()] * 3, *[quiet_voice(0.004)] * 20, *[speech()] * 3)

    audio = stt._record(mic)

    assert (
        np.abs(audio) > 0.1
    ).sum() == 3 * stt.BLOCK  # stopped before the second burst


def test_a_chime_right_after_the_wake_word_cannot_end_the_recording_early():
    # chime, then a pause longer than the end-of-speech silence, then the command
    mic = reader(*[speech()] * 2, *[silence()] * 15, *[speech()] * 8)

    audio = stt._record(mic, after_wake=True)

    assert (np.abs(audio) > 0.1).sum() == (2 + 8) * stt.BLOCK  # everything is kept


def test_speech_straight_after_the_wake_word_is_kept_from_its_first_block():
    mic = reader(*[speech()] * 8)

    audio = stt._record(mic, after_wake=True)

    assert (np.abs(audio) > 0.1).sum() == 8 * stt.BLOCK  # nothing lost


def test_a_chime_and_then_nothing_gives_no_recording():
    mic = reader(*[speech()] * 2)

    assert stt._record(mic, after_wake=True) is None


def test_a_blip_too_short_to_be_a_command_gives_no_recording():
    mic = reader(*[speech()] * (stt.MIN_COMMAND_BLOCKS - 1))

    assert stt._record(mic, after_wake=True) is None


def test_recording_after_the_wake_word_still_stops_after_the_silence():
    mic = reader(*[speech()] * 8)

    audio = stt._record(mic, after_wake=True)

    trailing = len(audio) - 8 * stt.BLOCK
    assert 1.0 <= trailing / stt.SAMPLE_RATE < 1.2


def test_listen_after_the_wake_word_ignores_the_chime_and_hears_the_command(
    monkeypatch,
):
    heard = []

    class Whisper:
        def transcribe(self, audio, **_):
            heard.append(audio)
            return iter([SimpleNamespace(text="what time is it")]), SimpleNamespace(
                language="en", all_language_probs=[("en", 1.0)]
            )

    monkeypatch.setattr(stt, "_model", lambda: Whisper())
    loud = np.full(stt.BLOCK, 16384, dtype=np.int16)
    quiet = np.zeros(stt.BLOCK, dtype=np.int16)
    stream = BlockStream(*[loud] * 2, *[quiet] * 15, *[loud] * 8)

    assert stt.listen(stream, after_wake=True) == ("what time is it", "en")
    assert (np.abs(heard[0]) > 0.1).sum() == 10 * stt.BLOCK
