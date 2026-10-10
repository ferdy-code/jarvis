import functools
import re

from jarvis import config

SUPPORTED_LANGS = {"en", "id"}

# Function words that are unmistakable in one language. Replies are always
# English or Indonesian, and a reply has several of these.
INDONESIAN_WORDS = {
    "yang", "dan", "di", "ke", "dari", "dengan", "untuk", "ini", "itu", "adalah",
    "sudah", "telah", "akan", "saya", "anda", "kamu", "tidak", "bisa", "ada",
    "jam", "sekarang", "hari", "suara", "layar", "halo", "terima", "kasih",
    "kenapa", "karena", "bagaimana", "apa", "atau", "pada", "menjadi", "oleh",
    "sedang", "lagi", "pukul", "kabar", "kabarmu", "naik", "atas",
}  # fmt: skip
ENGLISH_WORDS = {
    "the", "is", "are", "it", "a", "an", "to", "of", "and", "you", "your", "i",
    "this", "that", "not", "has", "have", "was", "now", "at", "in", "on", "for",
    "with", "can", "will", "how", "what", "hello", "functions", "because",
}  # fmt: skip


def guess_lang(text: str) -> str:
    """'id' if the text has more Indonesian than English function words."""
    words = re.findall(r"[a-z]+", text.lower())
    indonesian = sum(word in INDONESIAN_WORDS for word in words)
    english = sum(word in ENGLISH_WORDS for word in words)
    return "id" if indonesian > english else "en"


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
    wav, _ = model.synthesize(text, voice_style=style, lang=lang)
    sounddevice.play(wav.squeeze(), model.sample_rate)
    sounddevice.wait()
