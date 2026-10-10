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

- [ ] **Autoplay:** Firefox starts a YouTube video with sound when Jarvis opens it. Firefox
  blocks audible autoplay by default. Test: open a video link from a script, and the user
  says whether it plays. If it is blocked, add a Firefox site exception or send the "play"
  key.
- [ ] **Window focus:** a background Jarvis can bring Firefox to the front and press keys,
  even though Windows limits focus stealing. Test: a script sends `k` (YouTube pause) to
  Firefox while another window is active.
- [ ] **Finding the video:** the first video can be found from YouTube's results page. Test:
  10 English and Indonesian song queries. If that is fragile, switch to `yt-dlp`.
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
- **YouTube or YouTube Music** for "putar lagu"?
- **Tabs:** should a new song replace the last one Jarvis opened, or open a new tab each time
  (they will pile up)?
