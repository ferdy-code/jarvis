import pytest

from jarvis import browser, tools


class Remote:
    """Stand-ins for Windows' playing state and the keyboard, recording the key presses.

    `playing` is what Windows says right now. `starts` says whether it would say so
    within a moment (a song change makes the state blink off for a second).
    """

    def __init__(self, monkeypatch, playing=True, starts=True, stops=True):
        self.keys = []
        self.playing = playing
        self.starts = starts
        self.stops = stops
        monkeypatch.setattr(tools.browser, "is_playing", lambda: self.playing)
        monkeypatch.setattr(tools.browser, "press_media_key", self.keys.append)
        monkeypatch.setattr(tools.browser, "wait_for_playing", self.wait_for_playing)

    def wait_for_playing(self, playing, seconds):
        if playing:
            return self.playing or self.starts
        return self.stops


def test_pause_stops_music_that_is_playing(monkeypatch):
    remote = Remote(monkeypatch, playing=True)

    assert tools.browser_control("pause") == "paused"
    assert remote.keys == ["play_pause"]


def test_pause_does_nothing_when_nothing_is_playing(monkeypatch):
    remote = Remote(monkeypatch, playing=False, starts=False)

    assert tools.browser_control("pause") == "nothing is playing"
    assert (
        remote.keys == []
    )  # Play/Pause is a toggle: pressing it now would start music


def test_pause_still_works_when_the_state_blinks_off_during_a_song_change(monkeypatch):
    remote = Remote(monkeypatch, playing=False, starts=True)

    assert tools.browser_control("pause") == "paused"
    assert remote.keys == ["play_pause"]


def test_pause_says_so_if_the_music_did_not_stop(monkeypatch):
    Remote(monkeypatch, playing=True, stops=False)

    assert tools.browser_control("pause").startswith("error:")


def test_resume_starts_paused_music(monkeypatch):
    remote = Remote(monkeypatch, playing=False, starts=True)

    assert tools.browser_control("resume") == "resumed"
    assert remote.keys == ["play_pause"]


def test_resume_does_not_toggle_music_that_is_already_playing(monkeypatch):
    remote = Remote(monkeypatch, playing=True)

    assert tools.browser_control("resume") == "already playing"
    assert remote.keys == []


def test_resume_says_so_when_there_is_nothing_to_resume(monkeypatch):
    Remote(monkeypatch, playing=False, starts=False)

    assert tools.browser_control("resume").startswith("error:")


@pytest.mark.parametrize(
    ("action", "key"), [("next", "next"), ("previous", "previous")]
)
def test_next_and_previous_press_the_media_key_and_confirm_the_music_plays(
    monkeypatch, action, key
):
    remote = Remote(monkeypatch, playing=True)

    result = tools.browser_control(action)

    assert remote.keys == [key]
    assert action in result and not result.startswith("error")


@pytest.mark.parametrize("action", ["next", "previous"])
def test_next_and_previous_do_not_give_up_because_the_state_blinked_off(
    monkeypatch, action
):
    # right after "next" the state can read "not playing" for a second; "previous" was refused
    remote = Remote(monkeypatch, playing=False, starts=True)

    result = tools.browser_control(action)

    assert remote.keys == [action]
    assert not result.startswith("error")


def test_next_says_so_if_nothing_plays_afterwards(monkeypatch):
    Remote(monkeypatch, playing=False, starts=False)

    assert tools.browser_control("next").startswith("error:")


def test_scroll_is_passed_to_the_browser(monkeypatch):
    scrolls = []
    monkeypatch.setattr(
        tools.browser,
        "scroll",
        lambda direction: scrolls.append(direction) or "scrolled",
    )

    assert tools.browser_control("scroll_down") == "scrolled"
    assert tools.browser_control("scroll_up") == "scrolled"
    assert scrolls == ["down", "up"]


def test_an_unknown_action_is_an_error(monkeypatch):
    remote = Remote(monkeypatch)

    assert tools.browser_control("explode").startswith("error:")
    assert remote.keys == []


def test_browser_control_is_a_safe_tool_with_a_fixed_list_of_actions():
    tool = tools.TOOLS["browser_control"]
    actions = tool.schema["function"]["parameters"]["properties"]["action"]["enum"]

    assert tool.dangerous is False
    assert actions == [
        "pause",
        "resume",
        "next",
        "previous",
        "scroll_down",
        "scroll_up",
    ]


# --- scrolling in browser.py: keys only go to a verified Firefox window


class Desktop:
    """Fake windows. The user is in `terminal`; Firefox windows are listed in `windows`."""

    def __init__(self, monkeypatch, windows, can_focus=True):
        self.windows = windows
        self.front = "terminal"
        self.can_focus = can_focus
        self.pressed = []
        self.pressed_while_front = []
        monkeypatch.setattr(browser, "_firefox_windows", lambda: self.windows)
        monkeypatch.setattr(browser, "_front_window", lambda: self.front)
        monkeypatch.setattr(browser, "_bring_to_front", self.bring_to_front)
        monkeypatch.setattr(browser, "_press_key", self.press_key)
        monkeypatch.setattr(browser.time, "sleep", lambda seconds: None)
        monkeypatch.setattr(browser.config, "FIREFOX_PROFILE", "Keina Nara")

    def bring_to_front(self, window):
        if window != "terminal" and not self.can_focus:
            return False
        self.front = window
        return True

    def press_key(self, code):
        self.pressed.append(code)
        self.pressed_while_front.append(self.front)


KEINA = (101, "Example Domain — Keina Nara — Mozilla Firefox")
FERDY = (202, "Muhammad Ferdy — Mozilla Firefox")


def test_scroll_down_presses_page_down_in_the_chosen_profile_window(monkeypatch):
    desktop = Desktop(monkeypatch, [FERDY, KEINA])

    result = browser.scroll("down")

    assert desktop.pressed == [0x22]
    assert desktop.pressed_while_front == [101]  # never the other profile's window
    assert result == "scrolled down"


def test_scroll_up_presses_page_up(monkeypatch):
    desktop = Desktop(monkeypatch, [KEINA])

    browser.scroll("up")

    assert desktop.pressed == [0x21]


def test_scroll_gives_the_focus_back_to_where_the_user_was(monkeypatch):
    desktop = Desktop(monkeypatch, [KEINA])

    browser.scroll("down")

    assert desktop.front == "terminal"


def test_scroll_sends_no_key_if_firefox_could_not_be_brought_to_the_front(monkeypatch):
    desktop = Desktop(monkeypatch, [KEINA], can_focus=False)

    result = browser.scroll("down")

    assert result.startswith("error:")
    assert desktop.pressed == []


def test_scroll_sends_no_key_if_the_profile_has_no_window(monkeypatch):
    desktop = Desktop(monkeypatch, [FERDY])

    result = browser.scroll("down")

    assert result.startswith("error:") and "Keina Nara" in result
    assert desktop.pressed == []


def test_scroll_refuses_other_directions(monkeypatch):
    desktop = Desktop(monkeypatch, [KEINA])

    with pytest.raises(ValueError):
        browser.scroll("sideways")
    assert desktop.pressed == []


class FakeUser32:
    """Records the input events sent while bringing a window to the front."""

    def __init__(self):
        self.events = []

    def IsIconic(self, window):
        return False

    def ShowWindow(self, window, how):
        self.events.append(("show", how))

    def keybd_event(self, code, scan, flags, extra):
        self.events.append(("key", code, flags))

    def mouse_event(self, flags, dx, dy, data, extra):
        self.events.append(("mouse", dx, dy))

    def SetForegroundWindow(self, window):
        self.events.append(("front", window))

    def GetForegroundWindow(self):
        return 7


def test_bringing_a_window_forward_never_taps_alt_because_that_toggles_firefoxs_menu(
    monkeypatch,
):
    user32 = FakeUser32()
    monkeypatch.setattr(browser, "_win", lambda: (user32, None, None))
    monkeypatch.setattr(browser.time, "sleep", lambda seconds: None)

    assert browser._bring_to_front(7) is True

    keys = [event for event in user32.events if event[0] == "key"]
    assert keys == []  # an Alt tap made every second scroll disappear into the menu bar
    assert ("front", 7) in user32.events
    assert user32.events.index(("mouse", 1, 0)) < user32.events.index(("front", 7))


def test_the_mouse_nudge_moves_one_pixel_and_back(monkeypatch):
    user32 = FakeUser32()
    monkeypatch.setattr(browser, "_win", lambda: (user32, None, None))

    browser.nudge_mouse()

    assert user32.events == [("mouse", 1, 0), ("mouse", -1, 0)]
