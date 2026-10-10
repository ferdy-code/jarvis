import pytest

from jarvis.language import detect_language


@pytest.mark.parametrize(
    "text",
    [
        "what time is it?",
        "Hello! How can I assist you today?",
        "turn the volume down",
        "it is Saturday",
    ],
)
def test_english_is_recognised_from_its_function_words(text):
    assert detect_language(text) == "en"


@pytest.mark.parametrize(
    "text",
    [
        "jam berapa sekarang?",
        "hari apa hari ini",
        "tolong kunci layar saya",
        "Volume telah dikurangi menjadi 80%.",
        "sekarang jam berapa ya",
    ],
)
def test_indonesian_is_recognised_from_its_function_words(text):
    assert detect_language(text) == "id"


@pytest.mark.parametrize(
    "text", ["kecilkan volume", "mute", "restart komputer", "PC", "", "18:32"]
)
def test_a_command_with_no_telling_words_is_not_guessed(text):
    assert detect_language(text) is None
