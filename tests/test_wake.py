from typing import ClassVar

import numpy as np

from jarvis import wake


def test_detection_returns_at_the_first_score_over_the_threshold():
    scores = iter([0.0, 0.2, 0.6, 0.9])
    reads = []

    def read_block():
        reads.append(1)
        return "block"

    found = wake._detect(read_block, lambda _block: next(scores), threshold=0.5)

    assert found == 0.6
    assert len(reads) == 3


def test_a_score_equal_to_the_threshold_counts():
    scores = iter([0.1, 0.5])

    assert wake._detect(lambda: "b", lambda _b: next(scores), threshold=0.5) == 0.5


class FakeStream:
    """Stands in for sounddevice.InputStream and records how it was used."""

    opened: ClassVar[list] = []

    def __init__(self, **settings):
        self.settings = settings
        self.closed = False
        self.reads = 0
        FakeStream.opened.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True

    def read(self, frames):
        self.reads += 1
        return np.zeros((frames, 1), dtype=np.int16), False


class FakeModel:
    def __init__(self, scores):
        self.scores = iter(scores)

    def predict(self, block):
        assert block.shape == (wake.BLOCK,)
        return {wake.KEY: next(self.scores)}


def test_waiting_listens_at_16khz_and_releases_the_microphone(monkeypatch):
    FakeStream.opened.clear()
    monkeypatch.setattr("sounddevice.InputStream", FakeStream)
    monkeypatch.setattr(wake, "_new_model", lambda: FakeModel([0.0, 0.0, 0.99]))

    assert wake.wait_for_wake_word() is None

    stream = FakeStream.opened[0]
    assert stream.settings == {
        "samplerate": 16000,
        "channels": 1,
        "dtype": "int16",
        "blocksize": 1280,
    }
    assert stream.reads == 3
    assert stream.closed


def test_every_wait_starts_with_a_fresh_model(monkeypatch):
    FakeStream.opened.clear()
    monkeypatch.setattr("sounddevice.InputStream", FakeStream)
    built = []

    def new_model():
        built.append(1)
        return FakeModel([0.99])

    monkeypatch.setattr(wake, "_new_model", new_model)

    wake.wait_for_wake_word()
    wake.wait_for_wake_word()

    assert len(built) == 2


def test_the_microphone_is_released_even_when_something_fails(monkeypatch):
    FakeStream.opened.clear()
    monkeypatch.setattr("sounddevice.InputStream", FakeStream)

    class Broken:
        def predict(self, _block):
            raise RuntimeError("model crashed")

    monkeypatch.setattr(wake, "_new_model", lambda: Broken())

    try:
        wake.wait_for_wake_word()
    except RuntimeError:
        pass

    assert FakeStream.opened[0].closed
