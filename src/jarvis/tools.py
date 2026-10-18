import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import psutil
from pycaw.pycaw import AudioUtilities

from jarvis import browser, music
from jarvis.web import web_lookup


@dataclass(frozen=True)
class Tool:
    fn: Callable[..., str]
    schema: dict
    dangerous: bool = False
    # Tools that, once called in a turn, make this one refuse (prompt-injection guard).
    refused_after: frozenset[str] = frozenset()


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
    try:
        browser.open_url(song.url)
    except ValueError as error:
        return f"error: {error}"
    if browser.wait_for_playing(True, 8):
        return f"playing '{song.title}' by {song.artist}"
    return (
        f"opened '{song.title}' by {song.artist}, but no sound started within 8 seconds; "
        "Firefox may be blocking autoplay for music.youtube.com"
    )


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
    refused_after: frozenset[str] = frozenset(),
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
    return Tool(fn, schema, dangerous, refused_after)


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
    "web_lookup": _tool(
        web_lookup,
        # Answers aloud. It never opens a page or a browser.
        # After remember and forget were added, "news today" called get_datetime first
        # in 3 of 126 samples in 3 of 5 runs; saying news is not a date question fixed
        # it (0 of 126 in 6 runs in a row).
        "Read something from the internet and say a short summary aloud, naming the "
        "source. Use it for the news of today or any day (the news is not a date "
        "question, so never check the date first), for an encyclopedia answer about "
        "a person, place or event, and for summarising a website whose address the "
        "user gives. It does not open anything on screen "
        "and cannot search Google. Questions you can answer yourself "
        "(general knowledge, maths, jokes, chat) get a normal spoken answer, never "
        "this tool.",
        properties={
            "kind": {
                "type": "string",
                "enum": ["news", "wiki", "page"],
                "description": "news = current headlines; wiki = encyclopedia "
                "article; page = summary of one website",
            },
            "query": {
                "type": "string",
                "description": "news: a short topic, or empty for the top stories; "
                "wiki: the user's question in full; page: the website address "
                "such as example.com",
            },
            "language": {
                "type": "string",
                "enum": ["en", "id"],
                "description": "The language the user is speaking",
            },
        },
        required=["kind", "query", "language"],
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
