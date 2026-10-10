"""Manual audio checks. These need speakers and a microphone, so no pytest.

uv run python scripts/smoke_audio.py tts            # configured voice (JARVIS_VOICE)
uv run python scripts/smoke_audio.py tts F1 M3      # compare chosen voices
uv run python scripts/smoke_audio.py tts all        # audition all 10 voices
"""

import argparse

from jarvis import tts

SAMPLES = {
    "en": "Hello, I am Jarvis. It is Saturday, 10 October 2026, 18:16. "
    "The volume is now 80%.",
    "id": "Halo, saya Jarvis. Sekarang hari Sabtu, 10 Oktober 2026, jam 18:15. "
    "Volume sekarang 80%.",
}


def audition(voices: list[str]) -> None:
    from jarvis import config

    names = tts._model().voice_style_names if voices == ["all"] else voices
    for voice in names or [config.VOICE]:
        for lang, text in SAMPLES.items():
            print(f"voice {voice} ({lang}): {text}")
            tts.speak(text, lang, voice=voice)


parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument("check", choices=["tts"])
parser.add_argument("voices", nargs="*")
args = parser.parse_args()
if args.check == "tts":
    audition(args.voices)
