# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Jarvis is a typed + voice ("Hey Jarvis") assistant for one Windows 11 PC, in English and Indonesian. A small local LLM (Qwen3.5-4B behind LlamaStash's OpenAI-compatible API) picks from a fixed list of tools. `SPEC.md` is the detailed design record (measurements, why each piece is the way it is); `README.md` is the user guide; `tasks/todo.md` logs each task and what real runs found.

## Commands

`python` is not on PATH (Store alias stub): always go through `uv`. While a `jarvis.exe` is running, `uv run` cannot rebuild it, so use `uv run --no-sync`.

```
uv sync
uv run jarvis                      # typed + voice
uv run jarvis --no-voice           # typed only, starts in a second
uv run jarvis --reset-memory       # asks, deletes saved facts + history, exits (no models load)
uv run pytest -q                   # unit tests (no network, no audio)
uv run pytest tests/test_brain.py::test_ask_returns_the_model_reply
uv run ruff check                  # ~400 rules are on by default; also: uv run ruff format
```

Checks against the real model (need LlamaStash running on :11435; run after ANY change to a tool, a tool description or `SYSTEM_PROMPT`):

```
uv run python scripts/check_tools.py 3          # tool choice; must read "wrong: 0 of 126"; it flips between runs, so run it 4+ times
uv run python scripts/check_conversation.py 3   # 3 lines, each must be full: "fresh data 75/75, reply language 75/75",
                                                # "with facts: fresh data 75/75, reply language 75/75",
                                                # "facts: right 18/18, reply language 27/27, unrelated clean 9/9"
uv run python scripts/smoke_audio.py mic|stt|wake|tts   # manual audio checks
```

Set `PYTHONIOENCODING=utf-8` when scripts print Indonesian text, or the console crashes on cp1252.

## Architecture

`app.py` wires everything: a typed loop on the main thread and a voice thread (wake word → `stt.listen` → brain → `tts.speak`) share one `Brain` behind a lock, and both share one microphone stream (`mic.py`). `Assistant` also owns spoken-vs-typed confirmation, the echo guard (ignores the mic while Jarvis speaks) and the 3-failure give-up.

`brain.py` is the tool-call loop (max 3 rounds, then a no-tools completion). Non-obvious rules:

- History is a list of whole turns (question, tool calls + results, reply), trimmed together. Keeping only reply text made the model claim actions without calling tools. Turns using `FORGOTTEN_TOOLS` (clock, battery, remember, forget) are not remembered.
- Tools with `dangerous=True` (`power`) only run after the `confirm` callback says yes; with no callback they never run.
- A reply containing `<tool_call>` (the model writing a call as text) is replaced by `GIVE_UP_MESSAGE`, never spoken.
- `language.detect_language` adds "The user is speaking X" to the system prompt when the words are clear.

`tools.py` holds the tool functions and the `TOOLS` registry (the JSON schema + description for each). Tool descriptions and the prompt are load-bearing for the 4B model: every added tool has shifted older behaviour (false shutdown requests, wrong reply language). Descriptions say which tool answers aloud vs opens a page; keep the language sentence LAST in `SYSTEM_PROMPT`. Don't copy test phrases into descriptions as examples.

Music playback:

- `browser.py`: opens `http(s)` URLs only, in the Firefox profile named by `JARVIS_FIREFOX_PROFILE` (found via Firefox's profile-group sqlite and launched with `--profile`); `is_playing` uses the Windows audio session state (pycaw), not loudness; play/pause media key; a one-pixel mouse nudge brings the window forward (tapping Alt toggles Firefox's menu bar).
- `music.py`: `ytmusicapi` search; `play_music` pauses current music, opens the song URL, and reports success only after sound is actually playing.
- `web.py`: the `web_lookup` tool (news = Google News RSS, wiki = Wikipedia openings, page = one http(s) address reduced to text with `html.parser`); the model summarises it with NO tools offered, text in `<web>` tags as data. Plain urllib, never imports `browser` (a test enforces it). DuckDuckGo is blocked on this network and Bing returned junk, so no search-engine scraping.
Audio: `stt.py` (faster-whisper small, CUDA with CPU fallback; needs the nvidia-cublas/cudnn `bin` folders on PATH, VAD + vocabulary prompt + en/id re-decode to curb hallucinations), `wake.py` (openwakeword `hey_jarvis`, a fresh model per wait), `tts.py` (Supertonic, CPU; Indonesian digits are spelled out as words because it misreads them).

Memory (off with `JARVIS_DB_FILE=off`: no file, no memory tools, prompt unchanged):

- `db.py`: SQLite file (`data/jarvis.sqlite3`), tables `turns` and `facts`, one connection per operation; refuses a newer `user_version`.
- `history.py`: saves each turn, keeps 100, loads the newest 10 under 12 h old. `FORGOTTEN_TOOLS` turns are neither kept nor saved; `UNSAVED_TOOLS` (`web_lookup`) are kept for the run but never written.
- `facts.py` (max 30, 3-200 chars, `looks_secret`) + `memory_tools.py` (`remember`, `forget`; `Tool.refused_after` makes them error in a turn that called `web_lookup`, so a web page cannot write memory). The facts block goes before `SYSTEM_PROMPT` (language sentence still last); a successful `forget` clears the saved history, or the old chat would bring the fact back.
- `netguard.py`: `web_lookup page` refuses non-public addresses and redirects to them.

`config.py` reads all settings from `JARVIS_*` env vars. `tests/test_readme.py` fails unless README documents exactly those settings, so add new ones to README too. `EXTRA_BODY` (thinking off, temperature 0) is sent only when the base URL is local.

## Working conventions

- Real-hardware and real-model runs have repeatedly found bugs unit tests could not; don't trust a pass until it has been repeated, and a harness must record calls to real tools.
- Only send keys to a Firefox window after verifying its title; close test tabs only by verified title.
- Shell here collapses `\n`/double backslashes in inline scripts: use the Edit/Write tools or `chr(92)` for such strings; put commit messages in a file and use `git commit -F`.
- Commits end with the `Co-Authored-By` / `Claude-Session` lines from the session's attribution reminder.

## Task delegation

- Delegate every implementation task to the `task-worker` subagent.
- When it finishes, show its report in the main window before moving on.
- For independent tasks, run multiple `task-worker` agents in parallel.
