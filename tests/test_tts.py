from types import SimpleNamespace

import numpy as np
import pytest

from jarvis import tts

# Replies copied from real runs of the model.
ENGLISH = [
    "It is Saturday 10 October 2026, 18:16.",
    "The volume is now at 80%.",
    "You have no battery because this is a desktop PC.",
    "The computer was not shut down.",
    "Python decorators are functions that extend other functions.",
    "Hello! How can I assist you today?",
    "Volume 90%.",
]
INDONESIAN = [
    "Sekarang jam 18:15.",
    "Hari ini adalah Sabtu, 10 Oktober 2026, pukul 18:15.",
    "Volume telah dikurangi menjadi 80%.",
    "Suara sudah disenyapkan.",
    "Layar sudah terkunci.",
    "Halo, saya baik terima kasih. Bagaimana kabarmu?",
    "Kenapa ayam tidak bisa naik ke atas?",
]


@pytest.mark.parametrize("reply", ENGLISH)
def test_english_replies_are_guessed_as_english(reply):
    assert tts.guess_lang(reply) == "en"


@pytest.mark.parametrize("reply", INDONESIAN)
def test_indonesian_replies_are_guessed_as_indonesian(reply):
    assert tts.guess_lang(reply) == "id"


class FakeModel:
    sample_rate = 44100

    def __init__(self):
        self.synthesized = []

    def get_voice_style(self, name):
        return f"style-{name}"

    def synthesize(self, text, voice_style, lang):
        self.synthesized.append((text, voice_style, lang))
        return np.ones((1, 4), dtype=np.float32), np.array([0.1])


@pytest.fixture
def speaker(monkeypatch):
    """A fake model and fake speakers; returns (model, list of played audio)."""
    model = FakeModel()
    played = []
    monkeypatch.setattr(tts, "_model", lambda: model)
    tts._style.cache_clear()
    monkeypatch.setattr(
        "sounddevice.play", lambda wav, rate: played.append((wav, rate))
    )
    monkeypatch.setattr("sounddevice.wait", lambda: None)
    return SimpleNamespace(model=model, played=played)


def test_speak_plays_the_synthesized_audio_flattened(speaker):
    tts.speak("Hello", "en", voice="M1")

    wav, rate = speaker.played[0]
    assert wav.shape == (4,)
    assert rate == 44100
    assert speaker.model.synthesized == [("Hello", "style-M1", "en")]


def test_speak_falls_back_to_english_for_other_languages(speaker):
    tts.speak("Bonjour", "fr", voice="M1")

    assert speaker.model.synthesized[0][2] == "en"


def test_speak_uses_the_configured_voice_by_default(speaker, monkeypatch):
    monkeypatch.setattr(tts.config, "VOICE", "F2")

    tts.speak("Halo", "id")

    assert speaker.model.synthesized[0][1] == "style-F2"


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        ("Sekarang jam 18:15.", "Sekarang jam delapan belas lima belas."),
        ("Jam 07:05", "Jam tujuh nol lima"),
        ("Jam 18:00", "Jam delapan belas nol nol"),
        ("Volume 90%.", "Volume sembilan puluh persen."),
        ("Baterai 85 persen", "Baterai delapan puluh lima persen"),
        (
            "10 Oktober 2026",
            "sepuluh Oktober dua ribu dua puluh enam",
        ),
        ("Tidak ada angka.", "Tidak ada angka."),
    ],
)
def test_indonesian_text_gets_its_numbers_spelled_out(text, spoken):
    assert tts.spell_numbers_id(text) == spoken


@pytest.mark.parametrize(
    ("number", "words"),
    [
        (0, "nol"),
        (10, "sepuluh"),
        (11, "sebelas"),
        (19, "sembilan belas"),
        (20, "dua puluh"),
        (100, "seratus"),
        (101, "seratus satu"),
        (215, "dua ratus lima belas"),
        (1000, "seribu"),
        (1999, "seribu sembilan ratus sembilan puluh sembilan"),
        (12000, "dua belas ribu"),
    ],
)
def test_indonesian_number_words(number, words):
    assert tts.spell_numbers_id(str(number)) == words


def test_numbers_it_cannot_say_are_left_alone():
    assert tts.spell_numbers_id("3,5 liter dan 1234567") == "3,5 liter dan 1234567"


def test_speak_spells_out_numbers_for_indonesian_only(speaker):
    tts.speak("Jam 18:15", "id", voice="M1")
    tts.speak("It is 18:15", "en", voice="M1")

    spoken = [text for text, _, _ in speaker.model.synthesized]
    assert spoken == ["Jam delapan belas lima belas", "It is 18:15"]
