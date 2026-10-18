# Jarvis /web (typed, fetch + fixed sources)

## Problem Statement
How might we let Jarvis fetch web content and give a short summary, without scraping
search engines and without adding a tool the 4B model must choose between?

## Recommended Direction
A typed-only `/web` command in the typed loop, outside the tool list.
- `/web <address>`: fetch the page (http/https only), reduce it to readable text, summarise
  it in a model call with NO tools offered, text wrapped in `<web>` tags as data.
- `/web news [topic]` and `/web wiki <topic>`: the Google News RSS and Wikipedia sources that
  worked before (restore from commit 702cae7 rather than rewrite).

Voice stays unchanged, so tool choice stays "wrong: 0 of 39". `/web` fetches with `urllib`
and never imports `browser`; only `play_music` uses Firefox.

## Key Assumptions to Validate
- [ ] urllib reaches ~10 real sites from this PC (DuckDuckGo was blocked). Test with a
  script before writing any feature code.
- [ ] Text extraction leaves usable text on news and blog pages (not just nav and cookie banners).
- [ ] The 4B model's summary of a truncated page is correct on ~10 pages checked by hand.
- [ ] I actually type /web at least a few times a week for two weeks.

## MVP Scope
In: `/web <address>`, `/web news`, `/web wiki`; http(s) only; no-tools summary; tests; README.
Out: voice, search, multi-page answers, logged-in pages.

## Not Doing (and Why)
- `/web` opening the browser: it fetches with urllib; Firefox stays reserved for `play_music`.
  A test should fail if the web module imports `browser`.
- Search-engine scraping: DuckDuckGo is blocked and Bing returned junk.
- A tool in TOOLS or a voice trigger: every added tool shifted older behaviour.
- JS rendering (headless browser): heavy, and a separate project.
- Following links or reading several pages: more failure surface.

## Open Questions
- Which text extractor: stdlib html.parser, or an added dependency?
- If fetch fails on most sites, do we move to a search API (Brave or Tavily key)?
- Should /web results be remembered in Brain history?
