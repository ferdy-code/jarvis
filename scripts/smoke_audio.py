"""Manual audio checks. These need speakers and a microphone, so no pytest.

uv run python scripts/smoke_audio.py mic            # live microphone level meter
uv run python scripts/smoke_audio.py stt            # say 5 commands, see the text
uv run python scripts/smoke_audio.py tts            # configured voice (JARVIS_VOICE)
uv run python scripts/smoke_audio.py tts F1 M3      # compare chosen voices
uv run python scripts/smoke_audio.py tts all        # audition all 10 voices
"""

import argparse
import time

import numpy as np

from jarvis import config, stt, tts

SAMPLES = {
    "en": "Hello, I am Jarvis. It is Saturday, 10 October 2026, 18:16. "
    "The volume is now 80%.",
    "id": "Halo, saya Jarvis. Sekarang hari Sabtu, 10 Oktober 2026, jam 18:15. "
    "Volume sekarang 80%.",
}


def audition(voices: list[str]) -> None:
    names = tts._model().voice_style_names if voices == ["all"] else voices
    for voice in names or [config.VOICE]:
        for lang, text in SAMPLES.items():
            print(f"voice {voice} ({lang}): {text}")
            tts.speak(text, lang, voice=voice)


def meter(seconds: int = 6) -> None:
    import sounddevice

    print(
        f"Speak normally for {seconds} s. Speech counts above {config.MIC_THRESHOLD}."
    )
    peak = 0.0
    with sounddevice.InputStream(
        samplerate=stt.SAMPLE_RATE, channels=1, dtype="float32", blocksize=stt.BLOCK
    ) as stream:
        for _ in range(seconds * stt.SAMPLE_RATE // stt.BLOCK):
            level = float(np.sqrt(np.mean(stream.read(stt.BLOCK)[0] ** 2)))
            peak = max(peak, level)
            mark = "SPEECH" if level > config.MIC_THRESHOLD else ""
            print(f"{level:7.4f} {'#' * min(int(level * 200), 60):60} {mark}")
    print(f"peak level {peak:.4f}")
    if peak < 0.001:
        print("The microphone is silent: check it is plugged in, not muted, and that")
        print("Settings > Privacy > Microphone allows desktop apps.")


def listen_rounds(rounds: int = 5) -> None:
    print("Loading Whisper...")
    stt.load()
    original = stt.transcribe

    def timed(model, audio):
        start = time.perf_counter()
        result = original(model, audio)
        print(
            f"  recorded {len(audio) / stt.SAMPLE_RATE:.1f}s, "
            f"transcribed in {time.perf_counter() - start:.2f}s"
        )
        return result

    stt.transcribe = timed
    for number in range(1, rounds + 1):
        print(
            f"\n[{number}/{rounds}] Speak a command now (stops after 1 s of silence)..."
        )
        text, lang = stt.listen()
        print(f"  heard ({lang}): {text!r}" if text else "  heard nothing")


parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument("check", choices=["tts", "stt", "mic"])
parser.add_argument("voices", nargs="*")
args = parser.parse_args()
if args.check == "tts":
    audition(args.voices)
elif args.check == "stt":
    listen_rounds()
else:
    meter()
