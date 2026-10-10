import re

# Function words that are unmistakable in one language. Everything Jarvis hears or
# says is English or Indonesian, and a sentence has several of these.
INDONESIAN_WORDS = {
    "yang", "dan", "di", "ke", "dari", "dengan", "untuk", "ini", "itu", "adalah",
    "sudah", "telah", "akan", "saya", "anda", "kamu", "tidak", "bisa", "ada",
    "jam", "sekarang", "hari", "suara", "layar", "halo", "terima", "kasih",
    "kenapa", "karena", "bagaimana", "apa", "atau", "pada", "menjadi", "oleh",
    "sedang", "lagi", "pukul", "kabar", "kabarmu", "naik", "atas", "berapa", "tolong",
}  # fmt: skip
ENGLISH_WORDS = {
    "the", "is", "are", "it", "a", "an", "to", "of", "and", "you", "your", "i",
    "this", "that", "not", "has", "have", "was", "now", "at", "in", "on", "for",
    "with", "can", "will", "how", "what", "hello", "functions", "because",
}  # fmt: skip


def detect_language(text: str) -> str | None:
    """'id' or 'en' when the function words make it clear, otherwise None.

    A short command such as "kecilkan volume" or "mute" shows nothing, and then
    the answer is None rather than a guess.
    """
    words = re.findall(r"[a-z]+", text.lower())
    indonesian = sum(word in INDONESIAN_WORDS for word in words)
    english = sum(word in ENGLISH_WORDS for word in words)
    if indonesian > english:
        return "id"
    if english > indonesian:
        return "en"
    return None
