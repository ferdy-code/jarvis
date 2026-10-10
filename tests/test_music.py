from types import SimpleNamespace

from jarvis import browser, music, tools


class FakeYTMusic:
    def __init__(self, results):
        self.results = results
        self.searches = []

    def search(self, query, filter=None, limit=None):
        self.searches.append((query, filter, limit))
        return self.results


def song_result(title="Hati-Hati di Jalan", artist="Tulus", video_id="E7kHvjvU6JY"):
    return {"title": title, "artists": [{"name": artist}], "videoId": video_id}


def test_the_best_matching_song_is_found(monkeypatch):
    fake = FakeYTMusic([song_result()])
    monkeypatch.setattr(music, "_client", lambda: fake)

    song = music.find_song("Tulus Hati-Hati di Jalan")

    assert song == music.Song("Hati-Hati di Jalan", "Tulus", "E7kHvjvU6JY")
    assert fake.searches == [("Tulus Hati-Hati di Jalan", "songs", 3)]


def test_a_song_opens_on_youtube_music():
    song = music.Song("Yellow", "Coldplay", "9qnqYL0eNNI")

    assert song.url == "https://music.youtube.com/watch?v=9qnqYL0eNNI"


def test_results_without_a_video_id_are_skipped(monkeypatch):
    broken = {"title": "No id", "artists": [{"name": "X"}]}
    monkeypatch.setattr(
        music,
        "_client",
        lambda: FakeYTMusic([broken, song_result("Yellow", "Coldplay", "abc")]),
    )

    assert music.find_song("yellow").video_id == "abc"


def test_a_song_with_no_artist_listed_still_works(monkeypatch):
    result = {"title": "Instrumental", "artists": None, "videoId": "zzz"}
    monkeypatch.setattr(music, "_client", lambda: FakeYTMusic([result]))

    assert music.find_song("instrumental").artist == "unknown artist"


def test_no_results_gives_none(monkeypatch):
    monkeypatch.setattr(music, "_client", lambda: FakeYTMusic([]))

    assert music.find_song("zzzzzz") is None


FOUND = music.Song("Hati-Hati di Jalan", "Tulus", "E7k")


class Stage:
    """Fakes for the search and the browser, recording the order things happen in."""

    def __init__(
        self,
        monkeypatch,
        song=FOUND,
        sound=True,
        search_error=None,
    ):
        self.events = []
        monkeypatch.setattr(tools.music, "find_song", self.find_song)
        monkeypatch.setattr(
            tools.browser, "pause_if_playing", lambda: self.events.append("pause")
        )
        monkeypatch.setattr(tools.browser, "open_url", self.open_url)
        monkeypatch.setattr(
            tools.browser,
            "wait_for_playing",
            lambda playing, seconds: (
                self.events.append(f"wait {playing} {seconds}") or sound
            ),
        )
        self.song = song
        self.search_error = search_error

    def find_song(self, query):
        self.events.append(f"find {query}")
        if self.search_error:
            raise self.search_error
        return self.song

    def open_url(self, url):
        self.events.append(f"open {url}")
        return "opened in Firefox (Keina Nara)"


def test_play_music_pauses_the_old_song_then_opens_the_new_one_and_waits_for_sound(
    monkeypatch,
):
    stage = Stage(monkeypatch)

    result = tools.play_music("Tulus Hati-Hati di Jalan")

    assert stage.events == [
        "find Tulus Hati-Hati di Jalan",
        "pause",
        "open https://music.youtube.com/watch?v=E7k",
        "wait True 8",
    ]
    assert result == "playing 'Hati-Hati di Jalan' by Tulus"


def test_play_music_does_not_claim_success_when_no_sound_starts(monkeypatch):
    Stage(monkeypatch, sound=False)

    result = tools.play_music("Tulus Hati-Hati di Jalan")

    assert not result.startswith("playing")
    assert "no sound started" in result
    assert "autoplay" in result


def test_play_music_says_when_no_song_matches(monkeypatch):
    stage = Stage(monkeypatch, song=None)

    result = tools.play_music("qwertyuiop")

    assert result.startswith("error: no song found")
    assert stage.events == ["find qwertyuiop"]  # nothing paused or opened


def test_play_music_says_when_the_search_service_fails(monkeypatch):
    stage = Stage(monkeypatch, search_error=ConnectionError("offline"))

    result = tools.play_music("Coldplay Yellow")

    assert result.startswith("error: could not search YouTube Music")
    assert "offline" in result
    assert stage.events == ["find Coldplay Yellow"]


def test_play_music_refuses_an_empty_request(monkeypatch):
    stage = Stage(monkeypatch)

    assert tools.play_music("   ").startswith("error:")
    assert stage.events == []


def test_play_music_passes_on_a_browser_error(monkeypatch):
    stage = Stage(monkeypatch)

    def refuse(url):
        raise ValueError("that is not a web address")

    monkeypatch.setattr(tools.browser, "open_url", refuse)

    assert tools.play_music("x").startswith("error:")
    assert "wait True 8" not in stage.events


def test_play_music_is_a_safe_tool_that_describes_itself():
    tool = tools.TOOLS["play_music"]
    description = tool.schema["function"]["description"]

    assert tool.dangerous is False
    assert "YouTube Music" in description
    assert tool.schema["function"]["parameters"]["required"] == ["query"]


# --- the helpers in browser.py that play_music relies on


class FakeSession:
    """One entry of Windows' list of programs that have an audio stream."""

    def __init__(self, program, state):
        self.Process = (
            None if program is None else SimpleNamespace(name=lambda: program)
        )
        self.State = state


def fake_sessions(monkeypatch, *sessions):
    from pycaw.pycaw import AudioUtilities

    monkeypatch.setattr(
        AudioUtilities, "GetAllSessions", staticmethod(lambda: list(sessions))
    )


def test_playing_means_a_firefox_audio_stream_is_active(monkeypatch):
    fake_sessions(monkeypatch, FakeSession("firefox.exe", 1))

    assert browser.is_playing() is True


def test_a_paused_firefox_is_not_playing_even_though_its_session_still_exists(
    monkeypatch,
):
    fake_sessions(monkeypatch, FakeSession("firefox.exe", 0))

    assert browser.is_playing() is False


def test_other_programs_playing_sound_do_not_count(monkeypatch):
    fake_sessions(
        monkeypatch,
        FakeSession("spotify.exe", 1),
        FakeSession(None, 1),
        FakeSession("firefox.exe", 0),
    )

    assert browser.is_playing() is False


def test_a_silent_moment_between_two_songs_still_counts_as_playing(monkeypatch):
    # the session stays active while the next track loads; only the loudness drops
    fake_sessions(monkeypatch, FakeSession("firefox.exe", 1))

    assert browser.is_playing() is True


def test_pause_if_playing_presses_the_key_only_when_sound_is_coming_out(monkeypatch):
    keys = []
    monkeypatch.setattr(browser, "press_media_key", keys.append)
    monkeypatch.setattr(browser, "wait_for_playing", lambda playing, seconds: True)

    monkeypatch.setattr(browser, "is_playing", lambda: False)
    assert browser.pause_if_playing() is False
    assert keys == []  # the key is a toggle: pressing it now would START a paused song

    monkeypatch.setattr(browser, "is_playing", lambda: True)
    assert browser.pause_if_playing() is True
    assert keys == ["play_pause"]


def test_wait_for_playing_returns_as_soon_as_the_state_matches(monkeypatch):
    states = iter([False, False, True])
    monkeypatch.setattr(browser, "is_playing", lambda: next(states))
    monkeypatch.setattr(browser.time, "sleep", lambda seconds: None)

    assert browser.wait_for_playing(True, seconds=5) is True


def test_wait_for_playing_gives_up_after_the_time(monkeypatch):
    clock = SimpleNamespace(now=0.0)
    monkeypatch.setattr(browser, "is_playing", lambda: False)
    monkeypatch.setattr(browser.time, "monotonic", lambda: clock.now)
    monkeypatch.setattr(
        browser.time,
        "sleep",
        lambda seconds: setattr(clock, "now", clock.now + seconds),
    )

    assert browser.wait_for_playing(True, seconds=1) is False
