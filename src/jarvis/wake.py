import os
import warnings

from jarvis import config
from jarvis.mic import BLOCK, open_stream

KEY = "hey_jarvis_v0.1"


def _new_model():
    import openwakeword
    from openwakeword.model import Model

    folder = os.path.dirname(openwakeword.__file__)
    path = os.path.join(folder, "resources", "models", "hey_jarvis_v0.1.onnx")
    with warnings.catch_warnings():
        # openwakeword asks onnxruntime for CUDA, which this build does not have
        warnings.filterwarnings("ignore", message=".*CUDAExecutionProvider.*")
        return Model(wakeword_model_paths=[path])


def _detect(read_block, score, threshold: float) -> float:
    """Read audio blocks until one scores at or above the threshold."""
    while True:
        value = score(read_block())
        if value >= threshold:
            return value


def wait_for_wake_word(stream=None) -> None:
    """Block until "hey jarvis" is heard.

    Pass the open microphone to keep using it afterwards for the command, so no
    audio is lost in between. With none given, the microphone is opened here and
    released when this returns.
    """
    # A new model each time: reset() keeps the old audio, so the last "hey
    # jarvis" would trigger again straight away. Building one takes 0.2 s.
    model = _new_model()
    if stream is None:
        with open_stream() as own:
            _listen_on(own, model)
    else:
        _listen_on(stream, model)


def _listen_on(stream, model) -> None:
    _detect(
        lambda: stream.read(BLOCK)[0][:, 0],
        lambda block: model.predict(block)[KEY],
        config.WAKE_THRESHOLD,
    )


def load() -> None:
    """Build a model now, so a problem shows up at start-up and not at 'hey jarvis'."""
    _new_model()
