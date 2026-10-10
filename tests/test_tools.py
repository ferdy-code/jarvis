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


class FakeEndpoint:
    """Stands in for pycaw's IAudioEndpointVolume."""

    def __init__(self, percent=50, muted=False):
        self.scalar = percent / 100
        self.muted = muted

    def GetMasterVolumeLevelScalar(self):
        return self.scalar

    def SetMasterVolumeLevelScalar(self, scalar, _context):
        self.scalar = scalar

    def SetMute(self, muted, _context):
        self.muted = bool(muted)


def fake_volume(monkeypatch, **kwargs):
    endpoint = FakeEndpoint(**kwargs)
    monkeypatch.setattr(tools, "_endpoint", lambda: endpoint)
    return endpoint


def test_volume_up_and_down_move_by_the_step(monkeypatch):
    endpoint = fake_volume(monkeypatch, percent=50)

    assert tools.set_volume("up") == "volume 60%"
    assert tools.set_volume("down", step=25) == "volume 35%"
    assert endpoint.scalar == 0.35


def test_volume_stays_between_0_and_100(monkeypatch):
    fake_volume(monkeypatch, percent=95)
    assert tools.set_volume("up") == "volume 100%"

    fake_volume(monkeypatch, percent=5)
    assert tools.set_volume("down") == "volume 0%"


def test_volume_up_unmutes(monkeypatch):
    endpoint = fake_volume(monkeypatch, percent=50, muted=True)

    tools.set_volume("up")

    assert endpoint.muted is False


def test_mute_and_unmute_keep_the_level(monkeypatch):
    endpoint = fake_volume(monkeypatch, percent=40)

    assert tools.set_volume("mute") == "muted"
    assert endpoint.muted is True
    assert tools.set_volume("unmute") == "unmuted, volume 40%"
    assert endpoint.muted is False
    assert endpoint.scalar == 0.4


def test_volume_rejects_an_unknown_direction(monkeypatch):
    endpoint = fake_volume(monkeypatch, percent=50)

    result = tools.set_volume("sideways")

    assert result.startswith("error:")
    assert endpoint.scalar == 0.5


def test_lock_pc_asks_windows_to_lock(monkeypatch):
    commands = []
    monkeypatch.setattr(tools.subprocess, "run", lambda cmd, **_: commands.append(cmd))

    assert tools.lock_pc() == "locked"
    assert commands == [["rundll32.exe", "user32.dll,LockWorkStation"]]


def test_volume_schema_lists_the_directions():
    schema = tools.TOOLS["set_volume"].schema["function"]["parameters"]

    assert schema["properties"]["direction"]["enum"] == [
        "up",
        "down",
        "mute",
        "unmute",
    ]
    assert schema["required"] == ["direction"]


def record_commands(monkeypatch):
    commands = []
    monkeypatch.setattr(tools.subprocess, "run", lambda cmd, **_: commands.append(cmd))
    return commands


def test_power_shutdown_and_restart_use_a_5_second_delay(monkeypatch):
    commands = record_commands(monkeypatch)

    assert "shutting down" in tools.power("shutdown")
    assert "restarting" in tools.power("restart")
    assert commands == [["shutdown", "/s", "/t", "5"], ["shutdown", "/r", "/t", "5"]]


def test_power_rejects_anything_else_without_running_a_command(monkeypatch):
    commands = record_commands(monkeypatch)

    assert tools.power("hibernate").startswith("error:")
    assert commands == []


def test_power_is_registered_as_dangerous_and_the_rest_are_not():
    assert tools.TOOLS["power"].dangerous is True
    assert [n for n, t in tools.TOOLS.items() if t.dangerous] == ["power"]


def test_wake_screen_nudges_the_mouse_and_does_not_claim_to_unlock(monkeypatch):
    nudges = []
    monkeypatch.setattr(tools, "_nudge_mouse", lambda: nudges.append(1))

    result = tools.wake_screen()

    assert nudges == [1]
    assert result.startswith("screen turned on")
    assert "sign in yourself" in result  # a locked PC stays locked


def test_wake_screen_is_a_safe_tool_that_says_what_it_cannot_do():
    tool = tools.TOOLS["wake_screen"]
    description = tool.schema["function"]["description"]

    assert tool.dangerous is False
    assert "cannot turn the screen off" in description
    assert "cannot unlock" in description
