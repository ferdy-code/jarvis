import os

from jarvis import config

SAMPLE_RATE = 16000
BLOCK = 1280  # 80 ms, the frame size the model expects
KEY = "hey_jarvis_v0.1"


def _new_model():
    import openwakeword
    from openwakeword.model import Model

    folder = os.path.dirname(openwakeword.__file__)
    path = os.path.join(folder, "resources", "models", "hey_jarvis_v0.1.onnx")
    return Model(wakeword_model_paths=[path])


def _detect(read_block, score, threshold: float) -> float:
    """Read audio blocks until one scores at or above the threshold."""
    while True:
        value = score(read_block())
        if value >= threshold:
            return value


def wait_for_wake_word() -> None:
    """Block until "hey jarvis" is heard, then release the microphone."""
    import sounddevice

    # A new model each time: reset() keeps the old audio, so the last "hey
    # jarvis" would trigger again straight away. Building one takes 0.2 s.
    model = _new_model()
    with sounddevice.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=BLOCK
    ) as stream:
        _detect(
            lambda: stream.read(BLOCK)[0][:, 0],
            lambda block: model.predict(block)[KEY],
            config.WAKE_THRESHOLD,
        )


def load() -> None:
    """Build a model now, so a problem shows up at start-up and not at 'hey jarvis'."""
    _new_model()
