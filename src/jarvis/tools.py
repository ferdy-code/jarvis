import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote_plus

import psutil
from pycaw.pycaw import AudioUtilities

from jarvis import browser, music


@dataclass(frozen=True)
class Tool:
    fn: Callable[..., str]
    schema: dict
    dangerous: bool = False


def get_datetime() -> str:
    return datetime.now().strftime("%A %d %B %Y, %H:%M")


def get_battery() -> str:
    battery = psutil.sensors_battery()
    if battery is None:
        return "no battery (this is a desktop PC)"
    source = "plugged in" if battery.power_plugged else "on battery power"
    return f"{battery.percent:.0f}% battery, {source}"


def _endpoint():
    return AudioUtilities.GetSpeakers().EndpointVolume


def set_volume(direction: str, step: int = 10) -> str:
    endpoint = _endpoint()
    level = round(endpoint.GetMasterVolumeLevelScalar() * 100)
    if direction == "mute":
        endpoint.SetMute(1, None)
        return "muted"
    if direction == "unmute":
        endpoint.SetMute(0, None)
        return f"unmuted, volume {level}%"
    if direction not in ("up", "down"):
        return f"error: direction must be up, down, mute or unmute, not {direction!r}"
    level = max(0, min(100, level + (step if direction == "up" else -step)))
    endpoint.SetMute(0, None)
    endpoint.SetMasterVolumeLevelScalar(level / 100, None)
    return f"volume {level}%"


def wake_screen() -> str:
    browser.nudge_mouse()
    return (
        "screen turned on. If the PC is locked, the lock screen is showing and "
        "you need to sign in yourself."
    )


def open_website(address: str) -> str:
    try:
        return browser.open_url(address)
    except ValueError as error:
        return f"error: {error}"


def search_web(query: str) -> str:
    query = query.strip()
    if not query:
        return "error: nothing to search for"
    return open_website("https://www.google.com/search?q=" + quote_plus(query))


def play_music(query: str) -> str:
    query = query.strip()
    if not query:
        return "error: nothing to play"
    try:
        song = music.find_song(query)
    except Exception as error:  # noqa: BLE001 - any network or service trouble
        return f"error: could not search YouTube Music ({error})"
    if song is None:
        return f"error: no song found for {query!r}"
    browser.pause_if_playing()  # otherwise the old song keeps playing under the new one
    opened = open_website(song.url)
    if opened.startswith("error"):
        return opened
    if browser.wait_for_playing(True, 8):
        return f"playing '{song.title}' by {song.artist}"
    return (
        f"opened '{song.title}' by {song.artist}, but no sound started within 8 seconds; "
        "Firefox may be blocking autoplay for music.youtube.com"
    )


def browser_control(action: str) -> str:
    """Pause, resume, skip and scroll. Play/Pause is a toggle, so "pause" must never
    start music and "resume" must never pause it: they check the playing state first."""
    if action == "pause":
        # a song change makes the state blink off for a moment, so give it time to return
        if not browser.wait_for_playing(True, 1.5):
            return "nothing is playing"
        browser.press_media_key("play_pause")
        return (
            "paused"
            if browser.wait_for_playing(False, 3)
            else "error: the music did not pause"
        )
    if action == "resume":
        if browser.is_playing():
            return "already playing"
        browser.press_media_key("play_pause")
        if browser.wait_for_playing(True, 3):
            return "resumed"
        return "error: nothing resumed; there may be no paused music"
    if action in ("next", "previous"):
        browser.press_media_key(action)  # not a toggle, so no need to check first
        if browser.wait_for_playing(True, 5):
            return f"skipped to the {action} song"
        return "error: nothing is playing; there may be no music to skip"
    if action in ("scroll_down", "scroll_up"):
        return browser.scroll(action.removeprefix("scroll_"))
    return f"error: unknown action {action!r}"


def lock_pc() -> str:
    subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True)
    return "locked"


def power(action: str) -> str:
    flags = {"shutdown": "/s", "restart": "/r"}
    if action not in flags:
        return f"error: action must be shutdown or restart, not {action!r}"
    subprocess.run(["shutdown", flags[action], "/t", "5"], check=True)
    verb = "shutting down" if action == "shutdown" else "restarting"
    return f"{verb} in 5 seconds"


def _tool(
    fn: Callable[..., str],
    description: str,
    properties: dict | None = None,
    required: list[str] | None = None,
    dangerous: bool = False,
) -> Tool:
    schema = {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }
    return Tool(fn=fn, schema=schema, dangerous=dangerous)


TOOLS: dict[str, Tool] = {
    "get_datetime": _tool(get_datetime, "Current local date, weekday and time."),
    "get_battery": _tool(get_battery, "Battery percentage and charging state."),
    "set_volume": _tool(
        set_volume,
        "Change the PC speaker volume, mute it, or turn the sound back on (unmute).",
        properties={
            "direction": {"type": "string", "enum": ["up", "down", "mute", "unmute"]},
            "step": {
                "type": "integer",
                "description": "Percent to change by (default 10).",
            },
        },
        required=["direction"],
    ),
    "lock_pc": _tool(lock_pc, "Lock the Windows screen."),
    "open_website": _tool(
        open_website,
        "Open a web page in the browser for the user to look at. It cannot read the page.",
        properties={
            "address": {
                "type": "string",
                "description": "Full web address, for example https://www.youtube.com",
            }
        },
        required=["address"],
    ),
    "play_music": _tool(
        play_music,
        "Play a song on YouTube Music in the browser. Give the song title and artist "
        "if known, for example 'Tulus Hati-Hati di Jalan'. Use it when the user asks "
        "to play or listen to a song or an artist. Replaces whatever is playing.",
        properties={
            "query": {
                "type": "string",
                "description": "Song title and/or artist, without words like 'play'",
            }
        },
        required=["query"],
    ),
    "browser_control": _tool(
        browser_control,
        "Remote control for the music and the browser: pause or resume the music, "
        "skip to the next or previous song, or scroll the page down or up. "
        "'Stop the music' and 'matikan musik' mean pause. "
        "'Skip this song', 'ganti lagu' and 'lagu berikutnya' mean next. "
        "'Lagu sebelumnya' and 'go back one song' mean previous.",
        properties={
            "action": {
                "type": "string",
                "enum": [
                    "pause",
                    "resume",
                    "next",
                    "previous",
                    "scroll_down",
                    "scroll_up",
                ],
            }
        },
        required=["action"],
    ),
    "search_web": _tool(
        search_web,
        # Without the "only when asked" wording the 4B model opened Google for
        # trivia and jokes (4 of 10 ordinary questions); with it, none.
        "Search Google for the user by opening the results page in the browser. "
        "Use it when the user asks to search, google or look something up online, "
        "or asks about things you cannot know such as today's news or weather. "
        "Questions you can answer yourself (facts, explanations, jokes, chat) get a "
        "normal spoken answer, never a search. "
        "It cannot read the results or answer the question.",
        properties={"query": {"type": "string", "description": "What to search for"}},
        required=["query"],
    ),
    "wake_screen": _tool(
        wake_screen,
        "Turn the screen on when it is off (wake the display). It cannot turn the "
        "screen off, and it cannot unlock a locked PC.",
    ),
    "power": _tool(
        power,
        # "how do I restart my computer?" asked for a restart 3 times in 3 with the
        # old text ("only when the user clearly asks"); with this wording, never.
        "Shut down or restart the PC. Call this only when the user gives a direct "
        "order to do it right now, such as 'shut down the PC' or 'matikan komputer'. "
        "Never call it for questions about how to shut down or restart, explanations, "
        "or when the user says goodnight.",
        properties={"action": {"type": "string", "enum": ["shutdown", "restart"]}},
        required=["action"],
        dangerous=True,
    ),
}
