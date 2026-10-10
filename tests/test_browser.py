import os
import sqlite3

import pytest

from jarvis import browser


@pytest.mark.parametrize(
    "address",
    [
        "https://www.youtube.com",
        "http://example.com/a?b=1&c=2",
        "https://music.youtube.com/watch?v=abc123",
    ],
)
def test_web_addresses_are_accepted_unchanged(address):
    assert browser.check_web_address(address) == address


def test_a_bare_domain_gets_https():
    assert browser.check_web_address("youtube.com") == "https://youtube.com"
    assert (
        browser.check_web_address("  github.com/jarvis ") == "https://github.com/jarvis"
    )


@pytest.mark.parametrize(
    "address",
    [
        "file:///C:/Windows/System32/cmd.exe",
        "javascript:alert(1)",
        "ms-settings:",
        "C:/Windows/notepad.exe",
        "ftp://example.org/file",
        "-new-window",
        "https://",
        "https://exa mple.com",
        "https://example.com/" + "a" * 3000,
        "youtube",
        "",
    ],
)
def test_anything_that_is_not_a_web_page_is_refused(address):
    with pytest.raises(ValueError, match="web address"):
        browser.check_web_address(address)


def make_firefox_folder(tmp_path):
    """A fake Firefox data folder with a profile list like the real one."""
    groups = tmp_path / "Profile Groups"
    groups.mkdir()
    connection = sqlite3.connect(groups / "abc123.sqlite")
    connection.execute("create table Profiles (id integer, path text, name text)")
    connection.execute(
        "insert into Profiles values (1, ?, 'Muhammad Ferdy')",
        (os.path.join("Profiles", "6XM0CwI5.Profile 1"),),
    )
    connection.execute(
        "insert into Profiles values (2, ?, 'Keina Nara')",
        (os.path.join("Profiles", "autkvekn.Profile 2"),),
    )
    connection.commit()
    connection.close()
    return str(tmp_path)


def test_a_profile_name_is_turned_into_its_folder(tmp_path):
    folder = make_firefox_folder(tmp_path)

    found = browser.profile_path("Keina Nara", folder)

    assert found == os.path.join(folder, "Profiles", "autkvekn.Profile 2")


def test_the_profile_name_is_matched_ignoring_case(tmp_path):
    folder = make_firefox_folder(tmp_path)

    assert browser.profile_path("keina nara", folder) is not None


def test_an_unknown_profile_gives_none(tmp_path):
    folder = make_firefox_folder(tmp_path)

    assert browser.profile_path("Nobody", folder) is None


def test_a_missing_profile_list_gives_none(tmp_path):
    assert browser.profile_path("Keina Nara", str(tmp_path)) is None


def test_an_unreadable_profile_list_gives_none(tmp_path):
    (tmp_path / "Profile Groups").mkdir()
    (tmp_path / "Profile Groups" / "broken.sqlite").write_bytes(b"not a database")

    assert browser.profile_path("Keina Nara", str(tmp_path)) is None


def test_opening_a_page_starts_firefox_in_the_chosen_profile(monkeypatch):
    commands = []
    monkeypatch.setattr(browser.config, "FIREFOX_PROFILE", "Keina Nara")
    monkeypatch.setattr(browser, "profile_path", lambda name: "C:/profiles/keina")
    monkeypatch.setattr(browser, "firefox_exe", lambda: "C:/firefox/firefox.exe")
    monkeypatch.setattr(
        browser.subprocess, "Popen", lambda command: commands.append(command)
    )

    message = browser.open_url("https://www.youtube.com")

    assert commands == [
        [
            "C:/firefox/firefox.exe",
            "--profile",
            "C:/profiles/keina",
            "-new-tab",
            "https://www.youtube.com",
        ]
    ]
    assert "Keina Nara" in message


def test_opening_a_page_refuses_non_web_addresses_before_starting_anything(monkeypatch):
    commands = []
    monkeypatch.setattr(
        browser.subprocess, "Popen", lambda command: commands.append(command)
    )

    with pytest.raises(ValueError):
        browser.open_url("file:///C:/Windows/System32/cmd.exe")

    assert commands == []


def test_an_unknown_profile_falls_back_to_the_default_browser_and_says_so(monkeypatch):
    opened = []
    monkeypatch.setattr(browser.config, "FIREFOX_PROFILE", "Nobody")
    monkeypatch.setattr(browser, "profile_path", lambda name: None)
    monkeypatch.setattr(browser.webbrowser, "open", lambda url: opened.append(url))

    message = browser.open_url("https://example.com")

    assert opened == ["https://example.com"]
    assert "'Nobody' not found" in message


def test_without_a_profile_setting_the_default_browser_is_used(monkeypatch):
    opened = []
    monkeypatch.setattr(browser.config, "FIREFOX_PROFILE", "")
    monkeypatch.setattr(browser.webbrowser, "open", lambda url: opened.append(url))

    browser.open_url("https://example.com")

    assert opened == ["https://example.com"]
