# Jarvis web summary (decided: one voice tool, `web_lookup`)

> Decision 2026-10-18: implemented on voice as the single tool `web_lookup`, not as a typed-only
> `/web` command. The sections below are updated to match; the typed-only plan is dropped.

## Problem Statement
How might we let Jarvis fetch web content and give a short spoken summary, without
scraping search engines and with as few new tools as possible for the 4B model?

## Recommended Direction
ONE voice tool, `web_lookup(kind, query, language)`, answering aloud (it opens nothing).
- `kind=page`: fetch the address (http/https only, a spoken `bbc.com` gets `https://`),
  reduce it to readable text with stdlib `html.parser`, summarise it in a model call with NO
  tools offered, text wrapped in `<web>` tags as data.
- `kind=news` and `kind=wiki`: the Google News RSS and Wikipedia sources that worked
  before (restored from commit 702cae7).
- Failures (timeout, 401/403, SSL error, under 300 characters of text) come back as "could
  not read that page"; nothing is guessed.

Everything fetches with `urllib` and never imports `browser`; only `play_music` uses Firefox.

## Key Assumptions to Validate
- [ ] urllib reaches ~10 real sites from this PC (DuckDuckGo was blocked). Test with a
  script before writing any feature code.
- [ ] Text extraction leaves usable text on news and blog pages (not just nav and cookie banners).
- [ ] The 4B model's summary of a truncated page is correct on ~10 pages checked by hand.
- [ ] I actually ask for web summaries a few times a week for two weeks.

## MVP Scope
In: `web_lookup` (page, news, wiki) by voice and typing; http(s) only; no-tools summary; tests; README.
Out: search, multi-page answers, logged-in pages.

## Not Doing (and Why)
- `web_lookup` opening the browser: it fetches with urllib; Firefox stays reserved for
  `play_music`. A test fails if the web module imports `browser`.
- Search-engine scraping: DuckDuckGo is blocked and Bing returned junk.
- More than one tool: every added tool shifted older behaviour, so news, wiki and page share
  one tool with a `kind` argument (check_tools: 0 wrong of 84 with it).
- JS rendering (headless browser): heavy, and a separate project.
- Following links or reading several pages: more failure surface.

## Open Questions
- Which text extractor: stdlib html.parser, or an added dependency?
- If fetch fails on most sites, do we move to a search API (Brave or Tavily key)?
- Should web results be remembered in Brain history? (For now they are, like any turn.)
