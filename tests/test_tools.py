from datetime import datetime
from types import SimpleNamespace

from jarvis import tools


def test_get_datetime_formats_weekday_date_and_time(monkeypatch):
    class FixedClock:
        @staticmethod
        def now():
            return datetime(2026, 10, 10, 17, 5)

    monkeypatch.setattr(tools, "datetime", FixedClock)

    assert tools.get_datetime() == "Saturday 10 October 2026, 17:05"


def test_get_battery_reports_percent_and_charging_state(monkeypatch):
    battery = SimpleNamespace(percent=85.4, power_plugged=True)
    monkeypatch.setattr(tools.psutil, "sensors_battery", lambda: battery)

    assert tools.get_battery() == "85% battery, plugged in"


def test_get_battery_reports_when_unplugged(monkeypatch):
    battery = SimpleNamespace(percent=40.0, power_plugged=False)
    monkeypatch.setattr(tools.psutil, "sensors_battery", lambda: battery)

    assert tools.get_battery() == "40% battery, on battery power"


def test_get_battery_on_a_pc_without_one(monkeypatch):
    monkeypatch.setattr(tools.psutil, "sensors_battery", lambda: None)

    assert tools.get_battery() == "no battery (this is a desktop PC)"


def test_registry_has_a_schema_named_after_each_tool():
    assert {"get_datetime", "get_battery"} <= set(tools.TOOLS)
    for name, entry in tools.TOOLS.items():
        assert entry.schema["function"]["name"] == name
        assert entry.schema["function"]["description"]
