import collections
import functools
import glob
import math
import os
import sys

import numpy as np

from jarvis import config, trace
from jarvis.mic import BLOCK, SAMPLE_RATE, open_stream

END_SILENCE_S = 1.0
MAX_RECORD_S = 15
MAX_WAIT_S = 6  # give up when nobody starts speaking
PREROLL_BLOCKS = 3  # keep a little audio from before the threshold was crossed
# After the wake word the chime and the end of "Jarvis" are loud too. A recording
# made straight after it only counts as a command, and can only end, once this
# much sound has been heard: those blips are 2-3 blocks, a command is far more.
MIN_COMMAND_BLOCKS = 6  # 0.48 s
LANGS = ("en", "id")

# Whisper writes down what it expects to hear, so give it our vocabulary. This
# fixed "kecilkan volume" heard as "kecilkan follow" and "lock my PC" as "Lie".
PROMPT = (
    "Jarvis. volume, mute, unmute, battery, baterai, lock my PC, shut down, "
    "restart, kunci layar, kecilkan volume, naikkan volume, jam berapa sekarang."
)


def _record(read_block, after_wake: bool = False) -> np.ndarray | None:
    """Collect audio blocks until speech has started and then ended.

    After the wake word everything is kept from the first block, so a command
    spoken straight after "Hey Jarvis" is whole, and the recording cannot end
    until MIN_COMMAND_BLOCKS of sound have been heard.
    """
    preroll = collections.deque(maxlen=PREROLL_BLOCKS)
    blocks: list[np.ndarray] = []
    loud_blocks = quiet_blocks = waited = 0
    # Round the waits up and the maximum down, so no limit is ever broken.
    end_blocks = math.ceil(END_SILENCE_S * SAMPLE_RATE / BLOCK)
    max_blocks = int(MAX_RECORD_S * SAMPLE_RATE / BLOCK)
    wait_blocks = math.ceil(MAX_WAIT_S * SAMPLE_RATE / BLOCK)
    while len(blocks) < max_blocks:
        block = read_block()
        level = float(np.sqrt(np.mean(block**2)))
        loud = level > config.MIC_THRESHOLD
        if after_wake:
            blocks.append(block)
            loud_blocks += loud
            if loud_blocks < MIN_COMMAND_BLOCKS:
                if len(blocks) >= wait_blocks:
                    return None  # only the chime, then nothing
                continue
        elif not blocks:
            if loud:
                blocks = [*preroll, block]
            else:
                preroll.append(block)
                waited += 1
                if waited >= wait_blocks:
                    return None
            continue
        else:
            blocks.append(block)
        # Quiet voices flicker around the threshold, so once speech has started
        # only half the threshold counts as silence.
        quiet_blocks = quiet_blocks + 1 if level < config.MIC_THRESHOLD / 2 else 0
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


def listen(stream=None, after_wake: bool = False) -> tuple[str, str]:
    """Record one spoken command and return (text, language); ('', 'en') if none came.

    Pass the open microphone that heard the wake word, so the first words of the
    command are not lost while a second one opens. With none given, it opens and
    closes the microphone itself. `after_wake` says the recording follows the wake
    word, so the chime cannot start or end it.
    """
    model = _model()
    # "record" runs from the end of the chime until you stop talking, so it includes
    # how long you spoke; "transcribe" is the time Whisper itself needed.
    with trace.span("record") as recording:
        if stream is None:
            with open_stream() as own:
                audio = _record_from(own, after_wake)
        else:
            audio = _record_from(stream, after_wake)
        recording.set(
            audio_s=None if audio is None else round(len(audio) / SAMPLE_RATE, 1)
        )
    if audio is None:
        return "", "en"
    with trace.span("transcribe") as transcription:
        text, lang = transcribe(model, audio)
        transcription.set(lang=lang, chars=len(text))
    return text, lang


def _record_from(stream, after_wake: bool = False) -> np.ndarray | None:
    def read_block():
        return stream.read(BLOCK)[0][:, 0].astype(np.float32) / 32768

    return _record(read_block, after_wake)


def mic_peak(seconds: float = 1.0) -> float:
    """Loudest sample (0-1) heard in the next moments; near 0 means a dead microphone."""
    import sounddevice

    warmup_blocks = 3  # the first blocks of a device are not real audio yet
    blocks = warmup_blocks + int(seconds * SAMPLE_RATE / BLOCK)
    with sounddevice.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=BLOCK
    ) as stream:
        heard = [stream.read(BLOCK)[0] for _ in range(blocks)]
    return float(np.abs(np.concatenate(heard[warmup_blocks:])).max())
