from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import psutil


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


def _tool(fn: Callable[..., str], description: str, dangerous: bool = False) -> Tool:
    schema = {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": description,
            "parameters": {"type": "object", "properties": {}},
        },
    }
    return Tool(fn=fn, schema=schema, dangerous=dangerous)


TOOLS: dict[str, Tool] = {
    "get_datetime": _tool(get_datetime, "Current local date, weekday and time."),
    "get_battery": _tool(get_battery, "Battery percentage and charging state."),
}
