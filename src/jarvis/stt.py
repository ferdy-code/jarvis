import collections
import functools
import glob
import math
import os
import sys

import numpy as np

from jarvis import config

SAMPLE_RATE = 16000
BLOCK = 1280  # 80 ms of audio
END_SILENCE_S = 1.0
MAX_RECORD_S = 15
MAX_WAIT_S = 6  # give up when nobody starts speaking
PREROLL_BLOCKS = 3  # keep a little audio from before the threshold was crossed
LANGS = ("en", "id")

# Whisper writes down what it expects to hear, so give it our vocabulary. This
# fixed "kecilkan volume" heard as "kecilkan follow" and "lock my PC" as "Lie".
PROMPT = (
    "Jarvis. volume, mute, unmute, battery, baterai, lock my PC, shut down, "
    "restart, kunci layar, kecilkan volume, naikkan volume, jam berapa sekarang."
)


def _record(read_block) -> np.ndarray | None:
    """Collect audio blocks until speech has started and then ended."""
    preroll = collections.deque(maxlen=PREROLL_BLOCKS)
    blocks: list[np.ndarray] = []
    quiet_blocks = 0
    # Round the waits up and the maximum down, so no limit is ever broken.
    end_blocks = math.ceil(END_SILENCE_S * SAMPLE_RATE / BLOCK)
    max_blocks = int(MAX_RECORD_S * SAMPLE_RATE / BLOCK)
    wait_blocks = math.ceil(MAX_WAIT_S * SAMPLE_RATE / BLOCK)
    waited = 0
    while len(blocks) < max_blocks:
        block = read_block()
        loud = float(np.sqrt(np.mean(block**2))) > config.MIC_THRESHOLD
        if not blocks:
            if loud:
                blocks = [*preroll, block]
            else:
                preroll.append(block)
                waited += 1
                if waited >= wait_blocks:
                    return None
            continue
        blocks.append(block)
        quiet_blocks = 0 if loud else quiet_blocks + 1
        if quiet_blocks >= end_blocks:
            break
    return np.concatenate(blocks)


def transcribe(model, audio: np.ndarray) -> tuple[str, str]:
    """Return (text, language), where language is always 'en' or 'id'."""
    options = {
        "beam_size": 1,
        "vad_filter": True,  # without it, noise became words ("Fussball")
        "condition_on_previous_text": False,
        "initial_prompt": PROMPT,
    }
    segments, info = model.transcribe(audio, **options)
    # Two-word commands are often detected as Spanish or Czech, so pick the
    # likelier of the two languages we speak and decode again if needed.
    probs = dict(info.all_language_probs or [])
    lang = max(LANGS, key=lambda code: probs.get(code, 0.0))
    if info.language in LANGS:
        lang = info.language
    else:
        segments, _ = model.transcribe(audio, language=lang, **options)
    return " ".join(s.text.strip() for s in segments).strip(), lang


def _put_cuda_libraries_on_path() -> None:
    """The nvidia-*-cu12 packages hold the DLLs; Windows finds them via PATH."""
    try:
        import nvidia
    except ImportError:
        return
    for base in nvidia.__path__:
        for folder in glob.glob(os.path.join(base, "*", "bin")):
            os.environ["PATH"] = folder + os.pathsep + os.environ["PATH"]


@functools.cache
def _model():
    _put_cuda_libraries_on_path()
    from faster_whisper import WhisperModel

    try:
        # int8_float16 uses 290 MB less GPU memory than float16 with the same accuracy.
        model = WhisperModel(
            config.WHISPER_MODEL, device="cuda", compute_type="int8_float16"
        )
        # CUDA problems only show up on first use, so run once now.
        transcribe(model, np.zeros(SAMPLE_RATE, dtype=np.float32))
    except Exception as error:  # noqa: BLE001 - any GPU trouble means use the CPU
        print(
            f"(Whisper GPU unavailable: {error}. Using the slower CPU.)",
            file=sys.stderr,
        )
        model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")
    return model


def load() -> None:
    """Load Whisper now, so the first command is not slow."""
    _model()


def listen() -> tuple[str, str]:
    """Record one spoken command from the microphone. ('', 'en') if none came."""
    import sounddevice

    model = _model()
    with sounddevice.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=BLOCK
    ) as stream:
        audio = _record(lambda: stream.read(BLOCK)[0][:, 0])
    if audio is None:
        return "", "en"
    return transcribe(model, audio)
