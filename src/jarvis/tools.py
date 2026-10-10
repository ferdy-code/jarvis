import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import psutil
from pycaw.pycaw import AudioUtilities


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
    "power": _tool(
        power,
        "Shut down or restart the PC. Only call this when the user clearly asks.",
        properties={"action": {"type": "string", "enum": ["shutdown", "restart"]}},
        required=["action"],
        dangerous=True,
    ),
}
