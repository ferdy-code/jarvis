from jarvis import browser


class FakeUser32:
    """Records the mouse events sent."""

    def __init__(self):
        self.events = []

    def mouse_event(self, flags, dx, dy, data, extra):
        self.events.append(("mouse", dx, dy))


def test_the_mouse_nudge_moves_one_pixel_and_back(monkeypatch):
    user32 = FakeUser32()
    monkeypatch.setattr(browser, "_win", lambda: (user32, None, None))

    browser.nudge_mouse()

    assert user32.events == [("mouse", 1, 0), ("mouse", -1, 0)]
