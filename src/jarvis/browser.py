import functools
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
MEDIA_KEYS = {"next": 0xB0, "previous": 0xB1, "play_pause": 0xB3}
PAGE_KEYS = {"down": 0x22, "up": 0x21}  # Page Down, Page Up


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


def is_playing() -> bool:
    """Is Firefox playing something? Asks Windows whether a Firefox audio stream is active.

    Not the loudness: that dips to silence while the next song loads, so "previous"
    was refused ("nothing is playing") straight after "next". The stream state stays
    active through a song change, drops to inactive the moment the music is paused,
    and is back within 0.2 s of resuming.
    """
    from pycaw.pycaw import AudioUtilities

    return any(
        session.State == 1  # 1: AudioSessionStateActive
        for session in AudioUtilities.GetAllSessions()
        if session.Process and "firefox" in session.Process.name().lower()
    )


def press_media_key(name: str) -> None:
    """Press a media key. Windows gives it to the browser's music player, whichever
    window is in front, so no window has to be focused."""
    import ctypes

    code = MEDIA_KEYS[name]
    ctypes.windll.user32.keybd_event(code, 0, 0x1, 0)  # 0x1: extended key
    ctypes.windll.user32.keybd_event(code, 0, 0x1 | 0x2, 0)  # 0x2: key up


def wait_for_playing(playing: bool, seconds: float) -> bool:
    """Wait until Firefox is (or is not) playing. False if the time ran out."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if is_playing() == playing:
            return True
        time.sleep(0.1)
    return is_playing() == playing


def pause_if_playing() -> bool:
    """Pause whatever Firefox is playing. Play/Pause is a toggle, so it is only
    pressed while something is playing: otherwise it would start a paused song."""
    if not is_playing():
        return False
    press_media_key("play_pause")
    wait_for_playing(False, 3)
    return True


@functools.cache
def _win():
    """user32 with the argument types the window calls below need."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetForegroundWindow.restype = wintypes.HWND
    return user32, ctypes, wintypes


def _firefox_windows() -> list[tuple[int, str]]:
    """(handle, title) of every visible Firefox window. A title ends with the name
    of its profile: "Example Domain — Keina Nara — Mozilla Firefox"."""
    user32, ctypes, wintypes = _win()
    found = []

    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, name, 256)
            if name.value == "MozillaWindowClass":
                title = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, title, 512)
                found.append((hwnd, title.value))
        return True

    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(callback(visit), 0)
    return found


def _front_window():
    return _win()[0].GetForegroundWindow()


def nudge_mouse() -> None:
    """Move the mouse one pixel and back. To Windows this is user input: it wakes a
    display that is off, and it lets this program take the front window."""
    mouse_event = _win()[0].mouse_event
    mouse_event(0x0001, 1, 0, 0, 0)  # 0x0001: move
    mouse_event(0x0001, -1, 0, 0, 0)


def _bring_to_front(window) -> bool:
    """Make this window the one in front. True only if it really is afterwards.

    Not done with a tap of Alt: in Firefox that toggles the menu bar, and the next
    key (the Page Down) then went into the menu, so every second scroll was lost.
    """
    user32 = _win()[0]
    if user32.IsIconic(window):
        user32.ShowWindow(window, 9)  # restore a minimised window
    nudge_mouse()
    user32.SetForegroundWindow(window)
    time.sleep(0.3)
    return user32.GetForegroundWindow() == window


def _press_key(code: int) -> None:
    user32 = _win()[0]
    user32.keybd_event(code, 0, 0, 0)
    user32.keybd_event(code, 0, 0x2, 0)


def scroll(direction: str) -> str:
    """Page Down or Page Up in the Firefox window of the chosen profile.

    The key is only sent once that window is verified to be in front, and the
    window the user was in gets the focus back.
    """
    key = PAGE_KEYS.get(direction)
    if key is None:
        raise ValueError(f"direction must be up or down, not {direction!r}")
    profile = config.FIREFOX_PROFILE
    marker = f"— {profile} —" if profile else ""
    window = next((hwnd for hwnd, title in _firefox_windows() if marker in title), None)
    if window is None:
        return f"error: no Firefox window found for the profile '{profile}'"
    previous = _front_window()
    if not _bring_to_front(window):
        return "error: could not bring Firefox to the front"
    try:
        _press_key(key)
        time.sleep(0.3)
    finally:
        if previous and previous != window:
            _bring_to_front(previous)
    return f"scrolled {direction}"
