# Jarvis + Browser

Decided with the user on 2026-10-10: Phase A, then Phase B, and no browser agent.

## Problem Statement

How might we let the user play, open and control things on the web by voice, and later ask
the web questions, without giving up Jarvis's safety rules or its 3-second responses?

## Recommended Direction

**Phase A, "browser hands".**

- "Putar lagu ..." plays the song in Firefox (the default browser).
- "Buka YouTube" or "search Google for ..." opens the page.
- "Pause", "next", "back", "scroll down" and "next tab" press browser shortcuts.

Jarvis goes online only to look up which video to open. Web text never reaches the model.
Every action is still a fixed tool, and only `http(s)` addresses can be opened, so no other
link types and no local files.

**Phase B, "web answers".** "What's the news today?": Jarvis searches, reads two or three
pages, and speaks a short answer naming the source. The step that reads web pages runs with
no tools at all, so a malicious page can make Jarvis say something wrong but never do
anything.

A comes first because it is what the user would use first ("putar lagu ..."), it is small,
and it keeps every existing guarantee. B builds on it once A is in daily use.

## Key Assumptions to Validate (before writing feature code)

- [x] **Autoplay: WORKS once allowed per site** (confirmed 2026-10-10 on the fourth test).
  By default Firefox blocks it: a track opened by its link stayed silent for 25 s, three
  times. It worked after the user allowed it for `music.youtube.com` through the lock icon
  in the address bar (Permissions > Autoplay > Allow Audio and Video) in the Keina Nara
  profile. That saved `https://music.youtube.com autoplay-media=1` in the profile's
  `permissions.sqlite` (the Autoplay > Settings dialog had saved nothing in any of the six
  profiles). Result: the song started 1.7 s after `browser.open_url`, kept playing, and the
  media Play/Pause key paused it, resumed it and paused it again (0.2 s each). Measured with
  Windows' audio meter. Lesson: read the saved file before trusting that a setting took
  effect.
- [~] **Window focus:** partly confirmed (2026-10-10). A background Python program can bring
  Firefox to the front (`SetForegroundWindow` after a tap of Alt), and the terminal gets the
  focus back afterwards. Page Down scrolled a test page and Ctrl+W closed a tab. Not
  confirmed: a plain letter key ("k" never arrived), Alt+Left (Back) and Ctrl+Tab. A second
  test tab did not open as a separate tab, so the tab-switching result is inconclusive.
  Decision: do not depend on focus for music. Use the **media keys**, which Windows delivers to
  the browser's media session without any window focus. **Confirmed:** Play/Pause stopped the
  user's music in 0.2 s, resumed it, and stopped it again (measured with the audio meter).
  Next and previous track use the same mechanism but were not pressed. Scroll (Page Down /
  Page Up) can stay focus-based because it is confirmed.
- [x] **Finding the track:** confirmed (2026-10-10). `ytmusicapi` (searched with
  `filter="songs"`, no login) resolved 9 of 9 named songs, English and Indonesian, to the
  right title and artist in 0.4-1.0 s. A vague request ("lagu santai buat kerja") returned a
  plausible song. It is a new dependency, so the user must approve adding it.
- [ ] **Query extraction:** the 4B model turns a spoken request into a clean search query and
  picks the right tool. Test: sampling like the earlier tool checks, plus the regression
  suites (`scripts/check_conversation.py`, the 12-command trial, the shutdown false
  alarms).
- [ ] *(Phase B)* A spoken web answer takes 8 s or less. Test: time it on 10 questions.

## MVP Scope (Phase A)

**In:**

- `play_youtube(query)` and `open_website(name or address)`
- `search_web(query)`, which opens a results page for the user to read
- `browser_control(action)`, from a fixed list of shortcuts
- Tests, model sampling, a run on the real Firefox, and the README.

**Out:** reading pages aloud, the web answers of Phase B, and anything that needs the user's
accounts.

## Progress

- **Firefox profile decided (2026-10-10): Keina Nara.** Jarvis opens everything in that profile (`JARVIS_FIREFOX_PROFILE`). The music plays there. The autoplay permission must be set in that profile.
- **Done: `open_website` and `search_web`**, plus the profile targeting. Checked with the real Firefox: the page opened in the Keina Nara window. Model sampling: 21/21 site requests with valid addresses, 15/15 searches, 30/30 ordinary questions opened nothing, and the other tools were unchanged.
- **Done: `play_music(query)`** (2026-10-10). Real run: `playing 'Hati-Hati di Jalan' by Tulus` in 4.7 s; a second request paused it and played `Yellow` (tab title "Yellow | YouTube Music"). Model: 21/21 phrasings with clean queries.
- **Next:** `browser_control` (pause, resume, next, previous with the media keys, confirmed for pause and resume; scroll with Page Down).

## Not Doing (and Why)

- **Browser agent (forms, buying, clicking):** a 4B model would fail too often, and the
  failures would happen on the user's logged-in accounts.
- **"Summarize the page I'm on":** Firefox does not let outside programs read its tabs, so
  this would need a browser extension, which is a separate project.
- **Opening non-web addresses** (`file:`, app links): they can launch programs on the PC.
- **Downloading files, or keeping any browsing history in Jarvis:** no need, and more risk.

## Open Questions

- **Phase B search source:** free scraping (no key, but it breaks when sites change) or a
  search API with a free key (sturdier, but the user would sign up)?
- ~~**YouTube or YouTube Music**~~ **Decided (2026-10-10): YouTube Music.** It is a JavaScript app, so the first result cannot be read from a plain page. Candidates to test: the `ytmusicapi` library (unofficial, no login needed for search), or finding the track on youtube.com and opening it as `music.youtube.com/watch?v=ID`.
- **Tabs:** should a new song replace the last one Jarvis opened, or open a new tab each time
  (they will pile up)?
