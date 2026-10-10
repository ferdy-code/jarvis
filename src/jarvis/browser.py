import glob
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import webbrowser
from urllib.parse import urlparse

from jarvis import config

MAX_ADDRESS_LENGTH = 2048
DEFAULT_FIREFOX = "C:/Program Files/Mozilla Firefox/firefox.exe"
LOUD = 0.005  # a Firefox audio level above this (0-1) means sound is coming out
MEDIA_KEYS = {"next": 0xB0, "previous": 0xB1, "play_pause": 0xB3}


def check_web_address(address: str) -> str:
    """Return a safe web address, or raise ValueError with a message the model can read.

    Only http and https pages may be opened: file:, javascript: and app links can
    start programs on the PC.
    """
    address = address.strip()
    first_part = address.split("/")[0]
    looks_like_a_domain = (
        "." in first_part
        and not first_part.startswith((".", "-"))
        and all(c.isalnum() or c in "-." for c in first_part)
    )
    if "://" not in address and looks_like_a_domain:
        address = "https://" + address  # "youtube.com" -> "https://youtube.com"
    parsed = urlparse(address)
    valid = (
        parsed.scheme in ("http", "https")
        and bool(parsed.hostname)
        and " " not in address
        and len(address) <= MAX_ADDRESS_LENGTH
        and address.isprintable()
    )
    if not valid:
        raise ValueError(
            "that is not a web address; give a full http or https address such as "
            "https://www.youtube.com"
        )
    return address


def profile_path(name: str, firefox_dir: str | None = None) -> str | None:
    """The folder of the Firefox profile with this display name, or None.

    Firefox's profile list lives in a database it keeps open and writes to, so a
    copy (with its -wal and -shm files) is read instead of the original.
    """
    firefox_dir = firefox_dir or os.path.join(
        os.environ["APPDATA"], "Mozilla", "Firefox"
    )
    for database in glob.glob(os.path.join(firefox_dir, "Profile Groups", "*.sqlite")):
        with tempfile.TemporaryDirectory() as temp:
            copy = os.path.join(temp, "profiles.sqlite")
            for suffix in ("", "-wal", "-shm"):
                if os.path.exists(database + suffix):
                    shutil.copy(database + suffix, copy + suffix)
            connection = sqlite3.connect(copy)
            try:
                row = connection.execute(
                    "select path from Profiles where lower(name) = lower(?)", (name,)
                ).fetchone()
            except sqlite3.Error:
                row = None
            finally:
                connection.close()
        if row:
            return os.path.join(firefox_dir, row[0])
    return None


def firefox_exe() -> str:
    import winreg

    key = "SOFTWARE" + chr(92) + "Microsoft" + chr(92) + "Windows" + chr(92)
    key += "CurrentVersion" + chr(92) + "App Paths" + chr(92) + "firefox.exe"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as handle:
            return winreg.QueryValueEx(handle, "")[0]
    except OSError:
        return DEFAULT_FIREFOX


def open_url(url: str) -> str:
    """Open a web page in the configured Firefox profile and say what happened."""
    url = check_web_address(url)
    name = config.FIREFOX_PROFILE
    if not name:
        webbrowser.open(url)
        return "opened in the default browser"
    folder = profile_path(name)
    if folder is None:
        webbrowser.open(url)
        return f"opened in the default browser (Firefox profile '{name}' not found)"
    subprocess.Popen([firefox_exe(), "--profile", folder, "-new-tab", url])
    return f"opened in Firefox ({name})"


def _firefox_peak() -> float:
    """The loudest level of Firefox's sound over the last third of a second (0-1).

    One reading can land in a quiet beat of a song, so take the best of four.
    """
    from pycaw.api.endpointvolume import IAudioMeterInformation
    from pycaw.pycaw import AudioUtilities

    peak = 0.0
    for _ in range(4):
        for session in AudioUtilities.GetAllSessions():
            if session.Process and "firefox" in session.Process.name().lower():
                meter = session._ctl.QueryInterface(IAudioMeterInformation)
                peak = max(peak, meter.GetPeakValue())
        time.sleep(0.1)
    return peak


def is_playing() -> bool:
    return _firefox_peak() > LOUD


def press_media_key(name: str) -> None:
    """Press a media key. Windows gives it to the browser's music player, whichever
    window is in front, so no window has to be focused."""
    import ctypes

    code = MEDIA_KEYS[name]
    ctypes.windll.user32.keybd_event(code, 0, 0x1, 0)  # 0x1: extended key
    ctypes.windll.user32.keybd_event(code, 0, 0x1 | 0x2, 0)  # 0x2: key up


def wait_for_sound(playing: bool, seconds: float) -> bool:
    """Wait until Firefox is (or is not) making sound. False if the time ran out."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if is_playing() == playing:
            return True
        time.sleep(0.1)
    return is_playing() == playing


def pause_if_playing() -> bool:
    """Pause whatever Firefox is playing. Play/Pause is a toggle, so it is only
    pressed when sound is coming out: otherwise it would start a paused song."""
    if not is_playing():
        return False
    press_media_key("play_pause")
    wait_for_sound(False, 3)
    return True
