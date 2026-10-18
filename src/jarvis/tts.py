import functools
import re

from jarvis import config, trace
from jarvis.language import detect_language

SUPPORTED_LANGS = {"en", "id"}


def guess_lang(text: str) -> str:
    """The voice language for a reply: 'id' if it is clearly Indonesian, else 'en'."""
    return detect_language(text) or "en"


ONES = ["nol", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan"]  # fmt: skip


def _id_number(n: int) -> str:
    if n < 10:
        return ONES[n]
    if n == 10:
        return "sepuluh"
    if n == 11:
        return "sebelas"
    if n < 20:
        return f"{ONES[n - 10]} belas"
    if n < 100:
        tens, ones = divmod(n, 10)
        return f"{ONES[tens]} puluh" + (f" {ONES[ones]}" if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        head = "seratus" if hundreds == 1 else f"{ONES[hundreds]} ratus"
        return head + (f" {_id_number(rest)}" if rest else "")
    thousands, rest = divmod(n, 1000)
    head = "seribu" if thousands == 1 else f"{_id_number(thousands)} ribu"
    return head + (f" {_id_number(rest)}" if rest else "")


def _spell_match(match: re.Match) -> str:
    hour, minute, number, percent = match.group("hour", "minute", "int", "percent")
    if hour:
        spoken_minute = "nol nol" if minute == "00" else _id_number(int(minute))
        if minute[0] == "0" and minute != "00":
            spoken_minute = f"nol {_id_number(int(minute))}"
        return f"{_id_number(int(hour))} {spoken_minute}"
    # shortcut: decimals and numbers of a million or more stay digits
    if match.group("decimal") or int(number) >= 1_000_000:
        return match.group(0)
    return _id_number(int(number)) + (" persen" if percent else "")


NUMBER = re.compile(
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\b"
    r"|(?P<int>\d+)(?P<decimal>[.,]\d+)?(?P<percent>\s*%)?"
)


def spell_numbers_id(text: str) -> str:
    """Supertonic misreads Indonesian digits (85 became 25), but words are perfect."""
    return NUMBER.sub(_spell_match, text)


@functools.cache
def _model():
    from supertonic import TTS  # heavy import, only when voice is used

    return TTS(auto_download=True)


@functools.cache
def _style(voice: str):
    return _model().get_voice_style(voice)


def load() -> None:
    """Load the model and the configured voice now, so the first reply is fast."""
    _style(config.VOICE)


def speak(text: str, lang: str, voice: str | None = None) -> None:
    import sounddevice

    model = _model()
    style = _style(voice or config.VOICE)
    lang = lang if lang in SUPPORTED_LANGS else "en"
    if lang == "id":
        text = spell_numbers_id(text)
    with trace.span("synthesize", chars=len(text), lang=lang):
        wav, _ = model.synthesize(text, voice_style=style, lang=lang)
    with trace.span("play"):
        sounddevice.play(wav.squeeze(), model.sample_rate)
        sounddevice.wait()
