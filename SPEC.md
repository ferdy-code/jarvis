# Spec: Jarvis MVP

Intent: [docs/intent/jarvis.md](docs/intent/jarvis.md) · Status: draft, awaiting approval · 2026-10-10

## Objective

Jarvis is a personal voice and text assistant that runs fully offline in the terminal on one Windows 11 PC. You type or say "Hey Jarvis …" in English or Indonesian. A local LLM works out what you mean, can call a small set of system actions, and Jarvis answers in text and out loud, in the language you used.

It's a learning project that should also be reliable enough for daily use, so the code is small, readable, and has no clever abstractions.

**User stories**
- I type `what time is it?` and get the answer printed and spoken.
- I say "Hey Jarvis, kecilkan volume", the volume goes down, and Jarvis confirms in Indonesian.
- I say "Hey Jarvis, shut down the PC" and Jarvis asks me to confirm before doing anything.
- I ask a general question ("explain Python decorators") and get a short spoken answer.

## Tech Stack

| Concern | Choice | Version (resolved 2026-10-10) |
|---|---|---|
| Runtime | Python, managed by uv | 3.14 (fallback 3.12 if a wheel is missing) |
| LLM | LlamaStash (llama.cpp), OpenAI-compatible, `Qwen3.5-4B-Q4_K_M` | — |
| LLM client | `openai` | 3.28.0 |
| Speech-to-text | `faster-whisper`, model `small`, CUDA | 1.2.1 |
| Wake word | `openwakeword`, bundled `hey_jarvis_v0.1.onnx` (loaded with `Model(wakeword_model_paths=[path])`, no download) | 0.4.0 |
| Text-to-speech | `supertonic` (Supertonic 3, CPU, `en` + `id`) | 1.3.1 |
| Audio I/O | `sounddevice` | 0.5.6 |
| Volume | `pycaw` | 20260927 |
| Battery | `psutil` | 7.2.2 |
| Dev | `pytest`, `ruff` | latest |

**Verified against the running LlamaStash:**
- `chat_template_kwargs: {"enable_thinking": false}` turns off Qwen's reasoning step. A tool call then returns in about 340 ms, compared with about 1.5 s with thinking on.
- Indonesian input picks the right tool (`"Kecilkan volume"` → `set_volume(direction="down")`).

## Modules

| Module | File | What it does | Depends on |
|---|---|---|---|
| `brain` | `brain.py` | Chat history, LLM calls, the tool-call loop | `system-tools` (registry only) |
| `system-tools` | `tools.py` | Tool functions + their JSON schemas | — |
| `tts` | `tts.py` | `speak(text, lang)` | — |
| `stt` | `stt.py` | Record until silence → `(text, lang)` | — |
| `wake` | `wake.py` | Block until "hey jarvis" is heard | — |
| `language` | `language.py` | Tells English from Indonesian by function words; None when unsure | — |
| `browser` | `browser.py` | Opens web pages in a chosen Firefox profile; says whether Firefox is playing; presses media keys; scrolls | — |
| `music` | `music.py` | Finds a song on YouTube Music (`ytmusicapi`) | — |
| `web` | `web.py` | Fetches Google News headlines or Wikipedia openings and has the model, with no tools, turn them into a short spoken answer | — |
| `app` | `app.py` | CLI entry, wires input → brain → output | all |

**Build order:** `brain` + `system-tools`, then `app` (typed chat), then `tts`, then `stt`, then `wake`.

### `system-tools`

Each tool is a plain function that returns a short string for the LLM to work into its reply.

| Tool | Args | Behaviour | Dangerous |
|---|---|---|---|
| `get_datetime` | — | Local date, time, weekday | no |
| `get_battery` | — | Percent + plugged in or not. Returns "no battery" on a desktop PC | no |
| `set_volume` | `direction: up\|down\|mute\|unmute`, `step: int = 10` | Changes the master volume through pycaw and returns the new level | no |
| `lock_pc` | — | `rundll32.exe user32.dll,LockWorkStation` | no |
| `wake_screen` | — | Moves the mouse one pixel and back (`mouse_event`), which wakes a display that is off. Measured: display OFF, then ON 0.24 s after the call. Returns a note that a locked PC stays locked | no |
| `open_website` | `address` | Opens an `http` or `https` page in Firefox through `browser.open_url`. A bare domain such as `youtube.com` gets `https://`. It cannot read the page | no |
| `search_web` | `query` | Opens a Google results page for the query (`https://www.google.com/search?q=...`). It cannot read the results. The description says to use it only when the user asks to google something or to see results, and to use `web_answer` when the user wants to be told the answer; without the "only when asked" wording the 4B model searched for trivia and jokes (4 of 10 ordinary questions) | no |
| `web_answer` | `kind`: `news` or `facts`; `query`; `language`: `en` or `id` | A spoken answer from the internet (see the `web` section). `news`: a short topic, or empty for the top stories. `facts`: the user's whole question. The result starts "Tell the user this, keeping the source's name, and call no more tools:" because without it the main model retold the answer and dropped the source, or went on to call other tools | no |
| `play_music` | `query` | Finds the best matching song with `ytmusicapi`, pauses whatever Firefox is playing (only if it is playing, because Play/Pause is a toggle), opens `music.youtube.com/watch?v=ID` in the Keina Nara profile, then waits up to 8 s for Firefox to start playing. Replies `playing 'Title' by Artist`, or says no sound started and autoplay may be blocked, so it never claims success on a silent page. Measured: 3.7-4.7 s, the old song paused before the new one, the tab title became the song's | no |
| `browser_control` | `action`: `pause`, `resume`, `next`, `previous`, `scroll_down`, `scroll_up` | `pause` and `resume` check the playing state first (Play/Pause is a toggle: "pause" must never start music, "resume" must never pause it) and report what really happened. `pause` waits up to 1.5 s for the state to be "playing" before answering "nothing is playing". `next` and `previous` press the media key (no toggle, so no check) and confirm music plays within 5 s. Scrolling sends Page Down or Page Up to the Keina Nara window, only after verifying that window is in front, then gives the focus back. Measured on real Firefox: pause 1.6 s, resume 1.0 s, `next` changed "Hati-Hati di Jalan" to "Monokrom" and `previous` returned | no |
| `power` | `action: shutdown\|restart` | `shutdown /s /t 5` or `shutdown /r /t 5` | **yes** |

- `TOOLS: dict[str, Tool]` holds `fn`, `schema` and `dangerous`. That's the only registry, with no plugin system.
- Tools never raise errors up to the brain. They catch errors and return a message like `"error: <message>"`.

### `brain`

- `Brain(client, model, tools, confirm)`: `confirm: Callable[[str], bool]` is injected by `app`, so `brain` never touches the terminal or the microphone.
- `ask(text: str, lang: str) -> str`:
  1. Appends the user message.
  2. Calls the LLM with `tools` and thinking turned off.
  3. For each tool call: if the tool is dangerous and `confirm()` returns False, the result is `"cancelled by user"`. Otherwise it runs the tool.
  4. Appends the results and calls the LLM again.
  5. Stops at a text reply, or after 3 rounds of tool calls.
- System prompt: you are Jarvis, keep replies short (1–3 sentences, because they're spoken), answer in the user's language (`lang` hint provided), use tools for time, battery, volume, lock and power, and never pretend to have done an action you didn't run.
- History is in memory only and lost on exit. It is a list of whole turns (the question, any tool calls with their results, and the reply), trimmed to the last 10 turns together, so a tool call is never cut from its result. Why whole turns: with only the reply text kept, the model never saw itself call a tool and, in a longer chat, answered "Musik sudah dipause" without calling one (the music kept playing). With tool calls kept, 9 of 9 music sequences ended correctly; with text only, 0 of 3.
- Turns that read the clock or battery (`FORGOTTEN_TOOLS`) are not remembered at all: a reading is out of date once spoken, and the model copied its old answer, in the old language, instead of asking again.
- The reply language is told to the model when `detect_language` (the shared function-word lists in `language.py`) is sure about the user's words ("The user is speaking Indonesian"); short commands such as "kecilkan volume" get no hint. A `lang` given by the caller wins.
- Prompt wording that matters, each found by a failing check: how-to questions get answers and only orders get actions; a greeting, goodnight or thank you is not a command; and the language sentence must stay last (with the how-to sentence after it the reply language was wrong 6 of 75 times). Adding a tool can shift all of this, so run the suites listed under Testing Strategy after every new tool.
- If the LLM server can't be reached, it returns the message "My brain is offline. Is LlamaStash running?" and doesn't crash.

### `tts`

- `speak(text: str, lang: str) -> None` uses Supertonic `TTS(auto_download=True)` with a preset voice (default `M2`, configurable), and plays the audio through `sounddevice`. It blocks until playback finishes.
- `lang` must be `en` or `id`. Anything else falls back to `en`.
- The model is loaded once and stays in memory. Voices: `M1`-`M5`, `F1`-`F5`; output is 44.1 kHz. First run downloads about 385 MB to `~/.cache/supertonic3`.
- For `id`, numbers are spelled out as Indonesian words before synthesis (`spell_numbers_id`). Supertonic misreads Indonesian digits ("85 persen" was heard as "25%", "18:15" as "12.15"); written as words they were heard correctly 8 times out of 8. English digits are read fine.
- `guess_lang(reply)` picks `en` or `id` for typed turns by counting function words in the reply. Voice turns will use the language Whisper detected.

### `stt`

- `listen() -> tuple[str, str]` records from the default microphone at 16 kHz mono in 80 ms blocks. Speech starts when a block's loudness passes `JARVIS_MIC_THRESHOLD` (default 0.003: this PC's room is 0.0001 when quiet, a voice at the mic peaks near 0.25, a speaker across the room reaches only 0.002); it stops after 1.0 s of silence or 15 s total, and gives up if nobody speaks within 6 s. Once speech has started, only a level under half the threshold counts as silence, because quiet voices flicker around it. A little audio before the start is kept so the first word is not clipped. Audio is never written to disk.
- `listen(stream=None, after_wake=False)` can take the microphone that heard the wake word, so there is no gap in which the first words of the command are lost (a command spoken straight after "Hey Jarvis" arrived as just "PC." when a second microphone had to be opened). With `after_wake=True` everything is kept from the first block and the recording can neither start nor end until `MIN_COMMAND_BLOCKS` (6 blocks, 0.48 s) of sound have been heard, because the chime and the end of "Jarvis" are loud blips that would otherwise start the recording and end it before the command begins.
- Whisper runs as `small`, `int8_float16`, on the GPU (+399 MiB; float16 would need +751 MiB, and only about 900 MiB are free next to the Qwen model). It needs the CUDA 12 libraries from the `nvidia-cublas-cu12` and `nvidia-cudnn-cu12` packages, whose folders `stt` puts on `PATH` (`add_dll_directory` is not enough). If the GPU cannot be used, it prints a warning and falls back to CPU `int8`, which takes 2.7 s per phrase instead of 0.13 s. The first run ever spends about 25 s compiling kernels for the RTX 5060; later starts take 2-4 s.
- It returns `(text, lang)` with `lang` always `en` or `id`. Short commands are often detected as Spanish or Czech, so when another language wins, `stt` takes the likelier of `en` and `id` and decodes again with that language forced.
- Settings that mattered (46 synthetic commands plus noise): the speech filter (`vad_filter`) stops Whisper writing words for silence and room noise ("Fussball"), and the vocabulary prompt fixes "kecilkan follow" and "lock my pc" heard as "Lie". Spelling variants such as "computer" for "komputer" are left alone because the LLM understands them.
- It returns `("", "en")` when nothing was said.

### `wake`

- `wait_for_wake_word() -> None` streams the microphone in 80 ms chunks into openWakeWord's `hey_jarvis` model and returns when the score is ≥ 0.5 (threshold configurable).
- `wait_for_wake_word(stream=None)` normally gets the open microphone from `app`, which keeps it open for the command that follows (wake → stt on the same stream). With none given it opens the microphone itself and releases it on return, even on an error. The app closes the microphone before Jarvis answers, so Jarvis does not record its own voice.
- Every wait builds a fresh model (0.2 s). openWakeWord's `reset()` only clears the score history, not the audio buffers, so a reused model would fire again at once on the "hey jarvis" it just heard.
- Measured on synthetic speech (Supertonic, all 10 voices): "hey jarvis" scored 0.98-1.00 in 20 of 20 tries, also when a command followed it. 4 minutes of ordinary English and Indonesian speech and 2 minutes each of room and loud noise gave no trigger (max score 0.00 and 0.01). "Hey Marvin/Google/Siri/Davis" never trigger; anything containing "Jarvis" does, and "Hey Travis" 6 times in 10. Cost is 2.3 ms per 80 ms block (about 3% of one core). Scores are close to 0 or 1, so the 0.5 threshold is not delicate. The silero noise gate (`vad_threshold`) was not needed.
- Real-microphone numbers (4 of 5 hits, at most 1 false trigger in 30 minutes) still have to be measured with `scripts/smoke_audio.py wake`.

### `browser`

- `check_web_address(address)` is the safety rule: only `http` and `https` addresses with a host name, no spaces, no control characters and at most 2048 characters get through. `file:`, `javascript:`, `ms-settings:`, Windows paths and anything starting with `-` raise `ValueError`, whose message tells the model to give a full web address. The address is passed to Firefox as one list item, never through a shell.
- `open_url(url)` starts `firefox.exe --profile <folder> -new-tab <url>`. Windows hands a plain link to whichever Firefox profile answers first (it was Muhammad Ferdy's one time and Keina Nara's another), so the profile is chosen explicitly. `--profile` with the running profile's folder opens a tab in its existing window (checked).
- `profile_path(name)` finds the folder from Firefox's profile list, a SQLite database in `%APPDATA%/Mozilla/Firefox/Profile Groups` that Firefox keeps open, so a copy with its `-wal` and `-shm` files is read. The names there are the ones Firefox shows in window titles (this PC: Original profile, Muhammad Ferdy, Keina Nara, Naelya, Pewdy, Tiana). Matching ignores case. If the profile or the list is missing, the page opens in the default browser and the tool's reply says the profile was not found. An empty `JARVIS_FIREFOX_PROFILE` means the default browser.
- `firefox_exe()` reads the path from the `App Paths` registry key and falls back to `C:/Program Files/Mozilla Firefox/firefox.exe`.

### `browser`: playing state, media keys and scrolling

- `is_playing()` asks Windows (`pycaw`) whether a Firefox audio stream is **active**. The sound level was tried first and rejected: it dips to silence while a song loads, so "previous" was refused right after "next". The state drops to inactive the instant the music is paused and is back within 0.2 s of resuming (traced every 0.2 s). It can still blink off for a moment during a song change, which is why `pause`, `next` and `previous` are tolerant of that.
- `press_media_key("play_pause" | "next" | "previous")` sends the media key. Windows gives it to the browser's music player whichever window is in front, so no focus is needed. Pausing within the same instant as "next" correctly reports "the music did not pause" (the new song was still loading); half a second later it works.
- `scroll(direction)` finds the Firefox window whose title contains the profile name, brings it to the front, presses Page Down or Page Up, and gives the focus back. It brings the window forward with a one-pixel mouse nudge (`nudge_mouse`, shared with `wake_screen`), not a tap of Alt: in Firefox a tap of Alt toggles the menu bar, so every second Page Down was swallowed by the menu (found by a real test: 913, then nothing, then 1826...). With the nudge, six scrolls in a row all worked (913, 1826, 2739, 1826, 913, 1826).

### `music`

- `find_song(query)` takes the first of three `ytmusicapi` song results that has a video id and returns `Song(title, artist, video_id)`, or None. 9 of 9 named songs, English and Indonesian, matched the right title and artist in 0.4-1.0 s. The client is created once. It needs the internet but no login.

### `web`: spoken answers from the internet (Phase B)

- **Sources:** Google News RSS for `news` (6 headlines, each ends with its outlet; `hl`/`gl`/`ceid` pick Indonesia or the US) and the Wikipedia API of the user's language for `facts` (the openings of the 4 best matches, 500 characters each; the first match is often not the one with the answer: the capital of Australia is in "Canberra", not "Australia"). Both are documented, free, need no key and no new dependency (`urllib`). Search engines were tried and rejected: DuckDuckGo refuses connections on this network, Bing returned unrelated pages (a GitHub router project for "capital of Australia"), Brave, Mojeek and Startpage answered with captcha pages.
- **The reading step has no tools:** `_read` makes one chat request with a system prompt that calls the text between `<web>` tags data, never instructions, and offers no `tools`. A page can make the answer wrong but cannot make the reading step do anything. The answer is then returned to the main model, which does have tools (shutdown and restart still need a spoken yes), so this is a mitigation, not a wall.
- **Measured (real model, real network):** news 3.0-3.7 s from end of question to reply, facts 2.4-3.7 s. 13 of 14 fact questions answered correctly (the miss, the height of Everest in Indonesian, said honestly that the article does not give it); both unanswerable questions got "could not find it". The first version let the 4B reader mix two articles into a wrong date; the line "never combine facts from different articles" and a "could not find it" instruction fixed that.
- **Found by real runs:** (1) a "not found" result made the main model keep calling tools, open Google uninvited and finally write a tool call as text, which would have been spoken; the result now says to call no more tools, and `Brain` replaces a reply containing `<tool_call>` with a plain apology; (2) "cari di internet siapa itu X" went to `search_web` (6 of 75 samples) until both descriptions said which one answers aloud and which one opens a page; (3) the main model dropped the source's name until the result told it to keep it.
- **Limits:** Wikipedia rate-limits bursts (HTTP 429 after about 10 requests in a few seconds; one question at a time is far below that). Facts are only what is in the openings of 4 articles, so specific details often get "could not find it". News is headlines only: no article is opened or read.

### `app`

- `uv run jarvis` starts typed input plus voice. `uv run jarvis --no-voice` starts typed input only.
- **Main thread:** reads typed lines. `exit` or `quit` stops Jarvis.
- **Voice thread (daemon):** loops wake → beep → `stt.listen()` → `brain.ask()` → print + `tts.speak()`.
- One lock around `brain.ask` + `speak`, so typed and voice turns never overlap.
- **Language:** the model is not given a language hint (Whisper often labels two-word commands wrongly, and a wrong hint made the model answer in the wrong language); it answers in the language of the text it receives. The voice a reply is spoken in comes from the reply text (`tts.guess_lang`), for typed and voice turns alike. Whisper's language is used for one thing: the language of the spoken confirmation question.
- **Confirm:** a typed turn asks `[y/N]` on the terminal. A voice turn speaks the question ("Do you want me to run power action restart? Say yes or no.", or the Indonesian version), then `stt.listen()` and accepts `y`/`yes`/`yeah`/`ya`/`iya` (Whisper hears a spoken "ya" as "Yeah."). Anything else, including silence, counts as no.
- **Feedback:** after the wake word the terminal prints `(wake word heard - speak now)` and a short chime plays; the recognised command is shown as `you (voice)> ...`, and a spoken confirmation shows the question and the answer heard. "Hey Jarvis" heard again at the start of the command is removed before the brain sees it, and a command that was only the wake phrase counts as nothing heard.
- **Echo guard:** if the wake word fires while a turn is in progress (for example Jarvis saying its own name from a typed reply), it is ignored.
- **Start-up:** with voice on, Jarvis loads the voice (1.4 s), Whisper (2.0 s), the wake model (1.0 s) and checks the microphone for 1 s, about 6 s in all. Only a microphone that returns exactly zero (what a blocked microphone gives) gets a warning, not a shutdown: a quiet room is never exactly zero, but it is also only 0.0001, so a low peak says nothing.
- **Speed (everything real except the microphone and speakers):** Jarvis starts talking 2.6-3.1 s after the end of the user's speech, which includes the 1.04 s wait to notice the speech has ended. The limit is 4 s.
- **Graceful degradation:** if the microphone, Whisper, or the wake model fails to load, Jarvis prints a warning and runs typed-only. If TTS fails to load, it prints text only. It only exits on `exit` or Ctrl+C.

### Config (`config.py`)

Plain module-level constants, read once from environment variables with defaults. No config file.

| Env var | Default |
|---|---|
| `JARVIS_BASE_URL` | `http://127.0.0.1:11435/v1` |
| `JARVIS_MODEL` | `Qwen3.5-4B-Q4_K_M` |
| `JARVIS_API_KEY` | `llamastash` (stub, ignored by the loopback proxy) |
| `JARVIS_WHISPER_MODEL` | `small` |
| `JARVIS_MIC_THRESHOLD` | `0.003` |
| `JARVIS_VOICE` | `M2` |
| `JARVIS_WAKE_THRESHOLD` | `0.5` |
| `JARVIS_FIREFOX_PROFILE` | `Keina Nara` |

Switching to OpenAI means setting `JARVIS_BASE_URL=https://api.openai.com/v1`, `JARVIS_MODEL=<model>` and `JARVIS_API_KEY=<key>`, with no code changes. `enable_thinking` is sent only when the base URL is local.

## Commands

```
Install:      uv sync
Run:          uv run jarvis
Run (typed):  uv run jarvis --no-voice
Test:         uv run pytest -q
Lint:         uv run ruff check src tests
Format:       uv run ruff format src tests
Audio smoke:  uv run python scripts/smoke_audio.py   # mic → whisper → tts round trip, manual
LLM up?:      llamastash status
```

`python` is not on PATH on this machine, so always go through `uv run`.

## Project Structure

```
src/jarvis/__init__.py   → main() entry point (already wired in pyproject [project.scripts])
src/jarvis/app.py        → CLI loop, voice thread, confirm prompts
src/jarvis/brain.py      → LLM conversation + tool loop
src/jarvis/tools.py      → system tools + TOOLS registry
src/jarvis/tts.py        → Supertonic speak()
src/jarvis/stt.py        → record + faster-whisper listen()
src/jarvis/wake.py       → openWakeWord wait_for_wake_word()
src/jarvis/config.py     → env-var settings
tests/                   → pytest unit tests (tools, brain)
scripts/smoke_audio.py   → manual audio check
docs/intent/jarvis.md    → confirmed intent
SPEC.md                  → this file
```

## Code Style

- Functions first, classes only where there's state (`Brain`, model holders). Type hints on public functions.
- No comments that just repeat the code. Comment only the why (e.g. why the thinking flag is local-only).
- Heavy imports (`faster_whisper`, `openwakeword`, `supertonic`) happen inside the function that loads the model, so `--no-voice` starts instantly and tests don't need audio libs.
- `ruff format` defaults (88 columns, double quotes).

```python
# tools.py
from dataclasses import dataclass
from datetime import datetime
from typing import Callable


@dataclass(frozen=True)
class Tool:
    fn: Callable[..., str]
    schema: dict
    dangerous: bool = False


def get_datetime() -> str:
    return datetime.now().strftime("%A %d %B %Y, %H:%M")


TOOLS: dict[str, Tool] = {
    "get_datetime": Tool(
        fn=get_datetime,
        schema={
            "type": "function",
            "function": {
                "name": "get_datetime",
                "description": "Current local date and time.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ),
}
```

## Testing Strategy

- **pytest unit tests**, no network and no audio:
  - `tests/test_tools.py`: each tool with the OS calls monkeypatched (pycaw, psutil, `subprocess.run`). Checks argument validation and the `"error: …"` path.
  - `tests/test_brain.py`: `Brain` with a fake client that returns scripted responses. Covers a plain answer, a single tool call, a dangerous tool confirmed or refused, the 3-round tool-call cap, history trimming, and the server-down message.
- **Manual checks** (listed in the plan per task): `scripts/smoke_audio.py` for mic, Whisper and TTS; a real wake-word session; a real volume and lock run.
- **After every new tool or prompt change, run:** `scripts/check_conversation.py 3` (must read 75/75 and 75/75), the 12-command trial, the shutdown question/goodbye/order probe (0 false requests, every real order understood), and sampling of each tool group with ordinary questions that must open or run nothing. Three times a new tool made a different, older behaviour regress (restart question, goodnight, reply language), and a check that passed three rounds in a row failed later because the server state changed, so repeat before believing a pass.
- **Tool choice check:** `uv run python scripts/check_tools.py 3` (needs LlamaStash) sends 25 typical requests 3 times each to the real model with every tool replaced by a recorder, and checks the first tool and its main arguments (web answers, clock, volume, music, remote, pages, power, and ordinary questions that must call nothing). It must read `wrong: 0 of 75`.
- **Model behaviour check:** `uv run python scripts/check_conversation.py` (needs LlamaStash) runs multi-turn English/Indonesian chats against the real model with a clock that moves on every call, so a stale or wrong-language answer fails. Run it after any change to `SYSTEM_PROMPT` or the tool descriptions. The prompt wording is load-bearing with the 4B model and unit tests cannot see it.
- No coverage percentage target. Every function in `tools.py` and `brain.py` has at least one test.
- `uv run pytest -q` and `uv run ruff check` must pass before each commit.

## Boundaries

- **Always:**
  - Run tests and ruff before committing.
  - Keep `brain` free of I/O (inject `confirm`).
  - Confirm before `power`.
  - Keep everything working offline.
  - Use `uv add` for dependencies.
- **Ask first:**
  - Adding any dependency not in the Tech Stack table.
  - Adding a new tool, especially one that changes system state.
  - Changing the default model, the Python version, or the wake-word threshold logic.
  - Anything that writes outside the project directory.
- **Never:**
  - Call a cloud API by default.
  - Run `power` without an explicit yes.
  - Run arbitrary shell commands generated by the LLM. Tools are a fixed list.
  - Commit API keys or `.env` files.
  - Record or save microphone audio to disk.

## Unlocking is out of scope (decided 2026-10-10)

The user asked for Jarvis to log in when the PC is locked or the screen is off, and chose to wake the screen only. A locked Windows PC cannot be unlocked by a normal program: the sign-in screen runs on a protected desktop. The supported routes are Windows' own sign-in methods (Hello, PIN, or Voice Access on the sign-in screen, Windows 11 23H2 and later, which dictates a PIN and does not recognise voices) or a custom credential provider (native code loaded into the sign-in screen, which was judged too risky). Nothing in "Hey Jarvis" proves who is speaking, so a voice unlock would let anyone who says or plays the phrase in, and Supertonic can clone voices.

## Success Criteria

1. `uv sync` installs cleanly on this PC (Python 3.14, or 3.12 fallback recorded in this spec).
2. `uv run jarvis --no-voice`, then `what time is it?` → the correct local time is printed in **< 2 s**.
3. Typed `kecilkan volume` → system volume drops by 10, and the reply is in Indonesian.
4. Typed `shutdown the pc`, then `n` → nothing happens and Jarvis says it was cancelled. (The `y` path is checked once, manually.)
5. With LlamaStash stopped, Jarvis prints the "brain offline" message and keeps running.
6. `uv run jarvis` → saying "Hey Jarvis, what time is it?" gets a spoken answer that starts **≤ 4 s** after you stop talking.
7. The same works in Indonesian ("Hey Jarvis, jam berapa sekarang?"), with the answer spoken by the Indonesian voice.
8. The wake word triggers in ≥ 4 of 5 attempts at normal speaking distance, with ≤ 1 false trigger in a 30-minute session of normal room noise.
9. `uv run pytest -q` and `uv run ruff check src tests` pass.

## Open Questions

1. ~~**Supertonic voice**~~ **Resolved (Task 6):** the user chose `M2` after auditioning the presets (`M1`-`M5`, `F1`-`F5`).
2. ~~**Whisper size**~~ **Resolved (Tasks 7 and 9):** `small` stays. On the 46 synthetic commands it got 37 exactly (most misses are spelling variants), and with a person's voice at the microphone the full loop works. `medium` would not fit in the free GPU memory (about 900 MiB next to the Qwen model; `small` takes 399 MiB).
3. ~~**Python 3.14 wheels**~~ **Resolved (Task 1):** every dependency installs and imports on Python 3.14, so no fallback is needed. `ctranslate2` sees the GPU (CUDA, float16 supported). `onnxruntime` is CPU-only, which is fine for the wake word.
4. ~~**Wake-word chime**~~ **Resolved (Task 9):** yes. A 0.12 s beep plays after the wake word, together with the line `(wake word heard - speak now)`. It is played without waiting, because the microphone stays open from the wake word to the end of the command, and a second beep before the spoken confirmation is played to the end before the microphone opens.
