# Jarvis MVP: Tasks

Plan: [plan.md](plan.md) · Spec: [SPEC.md](../SPEC.md)

**Every task is done only when** its acceptance criteria are met, `uv run pytest -q` and `uv run ruff check src tests` pass, it has been run for real (not just tested), and it is committed.

---

## Phase 1: Typed Jarvis

### Task 1: Install dependencies and dev tooling ✅
**Description:** Add all runtime and dev dependencies from the SPEC Tech Stack and prove that every heavy package actually imports on this machine. This answers the Python 3.14 question before any feature code exists. Make the first commit.

**Acceptance criteria:**
- [ ] `uv sync` succeeds, and `uv run python -c "import openai, faster_whisper, openwakeword, supertonic, sounddevice, pycaw, psutil"` exits 0
- [ ] If 3.14 fails, `.python-version`, `requires-python` and SPEC are switched to 3.12 and the reason is noted in SPEC
- [ ] `pytest` and `ruff` are dev dependencies, and `uv run pytest -q` runs (0 tests is OK)

**Verification:**
- [ ] The import command above prints nothing and exits 0
- [ ] `uv run ruff check src tests` passes
- [ ] First commit on branch `main`

**Dependencies:** None
**Status:** done. Python 3.14 kept. openwakeword resolved to 0.4.0 (ONNX model is bundled), recorded in SPEC.
**Files:** `pyproject.toml`, `uv.lock`, `.python-version` (maybe), `SPEC.md` (maybe)
**Scope:** S

---

### Task 2: Typed chat end to end ✅
**Description:** `uv run jarvis --no-voice` opens a prompt, sends what you type to the local LLM, and prints the reply. There are no tools yet. This creates `config.py`, the first version of `Brain` (system prompt, history trimmed to 20, thinking turned off on localhost, offline message), and the typed loop in `app.py`.

**Acceptance criteria:**
- [ ] Typing `hello` gets a short reply. Typing `halo, apa kabar?` gets an Indonesian reply
- [ ] With LlamaStash stopped, Jarvis prints "My brain is offline. Is LlamaStash running?" and keeps the prompt open
- [ ] `exit`, `quit` or Ctrl+C exits cleanly (no traceback)

**Verification:**
- [ ] `tests/test_brain.py`: plain answer, history trim, server-down message (fake client)
- [ ] Manual: the three checks above

**Dependencies:** Task 1
**Files:** `src/jarvis/config.py`, `src/jarvis/brain.py`, `src/jarvis/app.py`, `src/jarvis/__init__.py`, `tests/test_brain.py`
**Scope:** M

---

### Task 3: Time and battery answers ✅
**Description:** Add `tools.py` with the `Tool` dataclass and `TOOLS` registry, plus `get_datetime` and `get_battery`. `Brain` passes the tool schemas, runs the tool calls, feeds the results back, and stops after 3 rounds of tool calls.

**Acceptance criteria:**
- [ ] Typed `what time is it?` and `jam berapa sekarang?` print the correct local time in < 2 s (SPEC criterion 2)
- [ ] `battery?` returns the percent, or "no battery" on this desktop PC
- [ ] A tool that raises becomes `"error: …"` and Jarvis still answers

**Verification:**
- [ ] `tests/test_tools.py`: datetime format, battery present or absent (psutil faked)
- [ ] `tests/test_brain.py`: single tool call, the 3-round cap
- [ ] Manual: the two questions above

**Dependencies:** Task 2
**Files:** `src/jarvis/tools.py`, `src/jarvis/brain.py`, `tests/test_tools.py`, `tests/test_brain.py`
**Scope:** M

---

### Task 4: Volume control and lock ✅
**Description:** Add `set_volume(direction, step=10)` using pycaw (returns the new level) and `lock_pc()`. Both are non-dangerous tools.

**Acceptance criteria:**
- [ ] Typed `kecilkan volume` lowers the volume by 10 and the reply is in Indonesian (SPEC criterion 3)
- [ ] `mute` and `unmute` work, and the volume stays within 0–100
- [ ] `lock my pc` locks Windows

**Verification:**
- [ ] `tests/test_tools.py`: up, down and mute with a fake endpoint (clamping, bad direction gives `"error: …"`), lock calls the right command (`subprocess.run` faked)
- [ ] Manual: the volume change can be heard, and lock works once

**Dependencies:** Task 3
**Files:** `src/jarvis/tools.py`, `tests/test_tools.py`
**Scope:** S

---

### Task 5: Shutdown and restart with confirmation ✅ (real "y" run left to the user)
**Description:** Add a `power(action)` tool marked `dangerous=True`. `Brain` asks the injected `confirm` callback before running it. `app` supplies a terminal `y/n` prompt.

**Acceptance criteria:**
- [ ] Typed `shutdown the pc`, then `n`: nothing runs and Jarvis says it was cancelled (SPEC criterion 4)
- [ ] Typed `restart`, then `y`: runs `shutdown /r /t 5` (checked once manually, `shutdown /a` aborts it)
- [ ] Only `shutdown` and `restart` are accepted. Anything else gives `"error: …"`

**Verification:**
- [ ] `tests/test_brain.py`: confirmed vs refused (the fake tool is never called when refused)
- [ ] `tests/test_tools.py`: the correct command for each action, bad action rejected
- [ ] Manual: the `n` path, then one `y` path followed by `shutdown /a`

**Dependencies:** Task 3
**Files:** `src/jarvis/tools.py`, `src/jarvis/brain.py`, `src/jarvis/app.py`, `tests/test_tools.py`, `tests/test_brain.py`
**Scope:** M

---

## Checkpoint A: Typed Jarvis is usable every day
- [x] SPEC success criteria 1, 2, 3, 4, 5 and 9 pass (2026-10-10; #5 tested with a dead port, not by stopping LlamaStash)
- [x] 12 mixed EN/ID commands x3 plus 2 follow-ups on the 4B model: 0 wrong first calls in 36 runs, so no need for Qwen3-8B
- [ ] Human review before voice work

---

## Phase 2: Speaking Jarvis

### Task 6: Spoken replies with Supertonic 3 ✅ (voice M2 chosen by the user)
**Description:** `tts.speak(text, lang)` loads Supertonic once, synthesizes speech in `en` or `id`, and plays it with sounddevice. `app` speaks every reply in voice mode, uses the last-known language for typed turns, and falls back to text only if TTS fails to load. List the available voice presets and pick one with the user.

**Acceptance criteria:**
- [ ] `uv run jarvis`, typed `what time is it?`: the answer is printed **and** spoken in English. `jam berapa?` is spoken in Indonesian
- [ ] `--no-voice` never loads Supertonic (starts instantly)
- [ ] If Supertonic is broken (simulate with a bad `JARVIS_VOICE`), Jarvis prints a warning and keeps working text-only

**Verification:**
- [ ] `scripts/smoke_audio.py tts`: speaks one EN and one ID sentence and prints the available presets
- [ ] Manual: the checks above, and the voice is chosen (Open Question 1)

**Dependencies:** Task 2 (Checkpoint A recommended)
**Files:** `src/jarvis/tts.py`, `src/jarvis/app.py`, `src/jarvis/config.py`, `scripts/smoke_audio.py`
**Scope:** M

---

## Checkpoint B: Jarvis talks
- [ ] Spoken replies in both languages. `--no-voice` and the text-only fallback still work
- [ ] Human review (is the voice good enough for daily use?)

---

## Phase 3: Listening Jarvis

### Task 7: Speech-to-text with faster-whisper ✅ (code and GPU done; the real-microphone test is left to the user)
**Description:** `stt.listen()` records 16 kHz mono until 1.0 s of silence (or 15 s max), runs Whisper `small` on CUDA float16, and returns `(text, lang)`, with `lang` limited to `en` or `id`. Microphone audio is never written to disk.

**Acceptance criteria:**
- [ ] `scripts/smoke_audio.py stt`: saying "what time is it" prints `('what time is it', 'en')`. Saying "jam berapa sekarang" prints an `id` result
- [ ] Silence returns `("", lang)`. A recording longer than 15 s is cut off
- [ ] Transcription finishes in < 1.5 s after you stop speaking (most of the 4 s budget from SPEC criterion 6)

**Verification:**
- [ ] Smoke script, 5 EN + 5 ID phrases. Note the accuracy, then decide `small` vs `medium` (Open Question 2)
- [ ] `nvidia-smi` while Qwen and Whisper are both loaded: VRAM fits

**Dependencies:** Task 1
**Result:** GPU works with `nvidia-cublas-cu12` + `nvidia-cudnn-cu12` (+399 MiB, 0.13 s per phrase, versus 2.7 s on the CPU). See SPEC `stt`.
**Files:** `src/jarvis/stt.py`, `scripts/smoke_audio.py`
**Scope:** S

---

### Task 8: Wake-word detector ✅ (code done and checked on synthetic speech; the real-microphone test is left to the user)
**Description:** `wake.wait_for_wake_word()` streams the microphone in 80 ms chunks into openWakeWord's `hey_jarvis` model and returns when the score is ≥ `JARVIS_WAKE_THRESHOLD`.

**Acceptance criteria:**
- [ ] `scripts/smoke_audio.py wake` prints "WAKE" (with the score) each time "hey jarvis" is said
- [ ] Triggers in ≥ 4 of 5 attempts at normal distance, with ≤ 1 false trigger in 30 minutes of normal room noise (SPEC criterion 8). Tune the threshold if not
- [ ] The microphone is released when the function returns (so `stt` can open it)

**Verification:**
- [ ] Smoke-script session with tallied results recorded in the commit message

**Dependencies:** Task 1
**Files:** `src/jarvis/wake.py`, `scripts/smoke_audio.py`
**Scope:** S

---

### Task 9: Full voice loop in the app ✅ (built and checked with a scripted microphone; the real-microphone checks are left to the user)
**Carry over from Task 7:** accept `yeah` as a yes (Whisper hears a spoken `ya` as `Yeah.`; as `no` it fails safe but is annoying). Catch errors from `stt.listen()` in the voice thread, since a GPU out-of-memory can happen mid-run. (Correction: the mic reading 0.0001 in Task 7 was the real noise floor of a quiet room, not a dead microphone.)
**Description:** `uv run jarvis` starts a daemon voice thread that loops: wake word, then a short generated chime, then `stt.listen()`, then `brain.ask()`, then print and `speak()`. One lock keeps typed and voice turns from overlapping. Voice turns update the language. A voice `confirm` speaks the question and accepts yes, ya or iya. If the microphone, Whisper or wake model fails, Jarvis warns and stays typed-only.

**Acceptance criteria:**
- [ ] "Hey Jarvis, what time is it?" gets a spoken answer starting ≤ 4 s after you stop talking (SPEC criterion 6)
- [ ] "Hey Jarvis, jam berapa sekarang?" is answered in the Indonesian voice (SPEC criterion 7)
- [ ] "Hey Jarvis, restart the PC", then "tidak": cancelled. Typing while voice is active works and never overlaps speech

**Verification:**
- [ ] `tests/test_app.py` (optional, only if it stays simple): confirm-word parsing (`yes`, `ya`, `iya` count as yes, anything else as no)
- [ ] Manual: the three checks above, plus unplugging the mic gives typed-only with a warning

**Dependencies:** Tasks 5, 6, 7, 8
**Files:** `src/jarvis/app.py`, `src/jarvis/config.py`, `tests/test_app.py` (maybe)
**Scope:** M

---

### Task 10: README usage docs ✅
**Description:** Write the README: what Jarvis is, prerequisites (LlamaStash plus the model, uv), install and run commands, the env vars for switching to OpenAI, the list of voice commands, and troubleshooting (brain offline, no mic, VRAM).

**Acceptance criteria:**
- [ ] A fresh reader can go from clone to "Hey Jarvis" using only the README
- [ ] The env-var table matches `config.py`

**Verification:**
- [ ] Manual read-through, and the commands are copy-pasted and run once

**Dependencies:** Task 9
**Files:** `README.md`
**Scope:** XS

---

## Checkpoint C: MVP complete
- [x] SPEC success criteria 1-7 and 9 pass (2026-10-10): clean install from a fresh clone; typed time answer 0.66-0.73 s; "kecilkan volume" 100 -> 90 in Indonesian; shutdown with "n" cancelled; brain offline message; spoken answer starts 2.5-3.0 s after the end of speech (limit 4 s, scripted microphone); Indonesian question answered in Indonesian and spoken with the Indonesian setting; 144 tests and ruff pass.
- [x] Criterion 8, with the user's real voice (reported by the user, 2026-10-10): the wake word triggered 5 of 5 times and there were no false triggers. The length of the false-trigger watch was not stated. Synthetic evidence: 20 of 20 hits across 10 voices, no false trigger in 8 minutes of speech and noise.
- [x] SPEC Open Questions answered and SPEC updated
- [ ] Human review

---

## After the MVP

### Task 11: Wake the screen ✅
**Description:** The user asked for Jarvis to log in when the PC is locked or the screen is off. After a feasibility check and a security discussion they chose to wake the screen only (see SPEC "Unlocking is out of scope"). A `wake_screen` tool moves the mouse one pixel and back.

**Acceptance criteria:**
- [x] "wake up the screen" / "nyalakan layar" (8 phrasings, both languages) calls `wake_screen`; "turn off the screen", "matikan layar" and "screen off" call nothing, and never `power`
- [x] A display that is off comes back on: measured OFF, then ON 0.24 s after the call
- [x] Jarvis says that a locked PC stays locked and that it cannot turn the screen off
- [x] No regression: 0 wrong in 36 trial runs, 50/50 conversation check, 0/6 false shutdown requests

**Not tested:** behaviour while the PC is actually locked (a test would lock the user out). To do later if wanted: refuse `power` while the PC is locked.
**Files:** `src/jarvis/tools.py`, `tests/test_tools.py`, `README.md`, `SPEC.md`

### Task 12: Open websites and search, in the Keina Nara Firefox profile ✅
**Description:** First slice of the browser feature (`docs/ideas/jarvis-browser.md`). The user asked to "change Firefox user to Keina Nara": Firefox has six profiles, and a plain link opens in whichever answers first, so Jarvis now starts Firefox with an explicit `--profile`. New `browser.py`, tools `open_website` and `search_web`, setting `JARVIS_FIREFOX_PROFILE`.

**Acceptance criteria:**
- [x] Only `http`/`https` addresses are opened; `file:`, `javascript:`, Windows paths, `-flags`, spaces and over-long addresses are refused (24 tests)
- [x] A profile name becomes its folder from Firefox's profile list, case-insensitively; missing or unreadable list falls back to the default browser and says so
- [x] The real tools open a page in the Keina Nara window (verified by the window title ending "— Keina Nara")
- [x] The model: 21/21 "open a site" with a valid address, 15/15 searches, 30/30 ordinary questions open nothing, other tools unchanged
- [x] No regression: 0 wrong in 36 trial runs, 50/50 conversation check, 0/27 false shutdown requests and 18/18 real orders

**Found on the way:** adding the two tools made the 4B model open Google for trivia and jokes (4 of 10 ordinary questions) and ask to restart the PC for "how do I restart my computer?" (3 of 3). Stricter tool descriptions fixed both; the wording is recorded in comments above them.
**Files:** `src/jarvis/browser.py`, `src/jarvis/tools.py`, `src/jarvis/config.py`, `tests/test_browser.py`, `tests/test_tools.py`, `README.md`, `SPEC.md`

### Task 13: Play music on YouTube Music ✅
**Description:** "Putar lagu ..." plays the song in the user's Firefox profile (Keina Nara). New `music.py` (ytmusicapi), sound helpers in `browser.py` (Firefox's audio level through `pycaw`, media keys, `pause_if_playing`, `wait_for_sound`), tool `play_music`. Needs autoplay allowed for `music.youtube.com` in that profile, which the user set after three failed tests (the Autoplay > Settings dialog saved nothing; the lock-icon panel did).

**Acceptance criteria:**
- [x] "putar lagu Tulus Hati-Hati di Jalan" plays it: reply `playing 'Hati-Hati di Jalan' by Tulus`, sound confirmed by the audio meter (4.7 s)
- [x] A second request replaces the first: the old song is paused (meter silent during the switch), the window title becomes "Yellow | YouTube Music"
- [x] If no sound starts in 8 s the reply says so and mentions autoplay, instead of claiming success; no song found and search failures come back as errors (191 tests)
- [x] The model: 21/21 music phrasings with a clean query; other tools unchanged; ordinary and how-to questions run nothing (33/33)
- [x] No regression: 0 wrong of 36 trial runs, 75/75 data and 75/75 language in the long conversations, 0/27 false shutdown requests with 18/18 real orders

**Found on the way:** the new tool again pushed "how do I restart my computer?" into a restart request (3 of 3). A system-prompt sentence (questions get answers, only orders get actions) fixed it for every tool, but placed after the language sentence it broke the reply language (6 of 75 wrong); placed before it, 75/75.
**Not done:** the spoken reply overlaps the first seconds of the song; tabs pile up (one per song).
**Files:** `src/jarvis/music.py`, `src/jarvis/browser.py`, `src/jarvis/tools.py`, `src/jarvis/brain.py`, `tests/test_music.py`, `README.md`, `SPEC.md`

### Task 14: Voice remote (pause, resume, next, previous, scroll) and a sturdier conversation memory ✅
**Description:** `browser_control` tool, and the changes to `Brain` that real runs forced.

**Acceptance criteria:**
- [x] Pause, resume, next and previous work on real Firefox: pause 1.6 s, resume 1.0 s, `next` changed the song ("Hati-Hati di Jalan" to "Monokrom"), `previous` returned. A second "pause" says "nothing is playing" and does not start music; a second "resume" says "already playing" and does not pause
- [x] Scrolling works every time on a verified test page (913, 1826, 2739, 1826, 913, 1826) and gives the focus back
- [x] The exact typed sequence that failed (play, next, previous, next, pause, resume, pause, pause) ends with the music paused, twice, and every command that needed a tool called one
- [x] Model: 96/96 remote phrasings; a music phrase never asks to shut down the PC; ordinary questions 42/42 open or run nothing
- [x] No regression: 0 wrong of 36 trial runs, three conversation rounds of 75/75 data and 75/75 language, 0/42 false shutdown requests with 18/18 real orders (243 tests)

**Found on the way (each by a real run, not by the unit tests):**
1. Tapping Alt to bring Firefox forward toggled its menu bar, so every second scroll vanished. Fixed with the one-pixel mouse nudge.
2. The sound level blinks to silence while a song loads, so "previous" was refused after "next". `is_playing` now uses Windows' stream state, which drops the instant the music is paused and stays on through a song change; `next`/`previous` no longer check first, and `pause` waits 1.5 s.
3. The model said "Musik sudah dipause" without calling any tool (the music kept playing) because its history held only its own earlier claims. The history now keeps whole turns with their tool calls: 9 of 9 sequences ended correctly instead of 0 of 3.
4. The reply language and a copied old time came back whenever a tool was added. The user's language is now told to the model when clear (`language.py`), and clock/battery turns are forgotten.
5. Each new tool shifted older behaviour ("how do I restart my computer?", "goodnight" asking for a shutdown). Two prompt sentences fixed them; their order matters (language last).
**Files:** `src/jarvis/brain.py`, `src/jarvis/browser.py`, `src/jarvis/tools.py`, `src/jarvis/language.py`, `src/jarvis/tts.py`, `tests/test_remote.py`, `tests/test_language.py`, `tests/test_brain.py`, `README.md`, `SPEC.md`

### Task 15: Spoken web answers (Phase B) ✅
**Description:** `web_answer(kind, query, language)` tool and `web.py`: fetch Google News headlines or Wikipedia openings, and have the model, with no tools, turn them into a short spoken answer that names its source.

**Acceptance criteria:**
- [x] News and facts answers in English and Indonesian from the real web in 2.4-3.7 s (real model, real network)
- [x] The reading step is offered no tools and treats the excerpts as data
- [x] Facts: 13 of 14 questions correct, the miss was an honest "not found"; unanswerable questions say they could not find it
- [x] Tool choice: `scripts/check_tools.py 3` reads wrong 0 of 75 (web answers, every older tool, ordinary questions call nothing)
- [x] No regression: `scripts/check_conversation.py 3` 75/75 and 75/75; 254 tests, ruff clean

**Found on the way (real runs):**
1. DuckDuckGo refuses connections on this network and Bing returned unrelated pages, so search-engine scraping was dropped for Google News RSS and Wikipedia.
2. "cari di internet siapa itu X" opened Google (`search_web`) in 6 of 75 samples until both tool descriptions said which one answers aloud.
3. A "not found" result made the main model open Google uninvited and write a tool call as text. The result now says to call no more tools, and `Brain` replaces a reply containing `<tool_call>` with a plain apology.
4. The 4B reader once mixed two articles into a wrong date; "never combine facts from different articles" fixed it. The main model dropped the source's name until the result told it to keep it.
**Files:** `src/jarvis/web.py`, `src/jarvis/tools.py`, `src/jarvis/brain.py`, `scripts/check_tools.py`, `tests/test_web.py`, `tests/test_brain.py`, `README.md`, `SPEC.md`, `docs/ideas/jarvis-browser.md`

---

## Memory and web guard

Spec: [docs/SPEC-memory.md](../docs/SPEC-memory.md) · Plan: [plan.md](plan.md#implementation-plan-memory-and-web-guard). Spec Task 1 = 16, 2 = 17, 3 = 18 + 19, 4 = 20, 5 = 21. Tasks 16 and 21 are independent and may run in parallel. After each task, stop so the user can run the real-model checks on this PC.

**Before Task 16:** commit the pending tracing change (`uv run pytest tests/test_trace.py -q` passes) so each task's commit holds only its own files.

### Task 16: Database foundation ✅
**Description:** `db.connect(path)` opens or creates the SQLite file with schema v1 (`turns`, `facts`) and refuses a newer `user_version`. `config.DB_FILE` reads `JARVIS_DB_FILE` (default `data/jarvis.sqlite3`; `off` or empty gives `None`), with the same pattern as `TRACE_FILE`. Nothing uses the database yet.

**Acceptance criteria:**
- [x] The schema is created once and data survives reopening; a database with `user_version` 2 raises a clear error and is not changed
- [x] `JARVIS_DB_FILE=off` and `JARVIS_DB_FILE=` both give `config.DB_FILE is None`
- [x] README settings table has the `JARVIS_DB_FILE` row; `.gitignore` has `data/`

**Verification:**
- [x] `uv run pytest -q tests/test_db.py tests/test_readme.py`, then the full `uv run pytest -q` and `uv run ruff check src tests`
- [x] Manual: `uv run python -c "from jarvis import db; db.connect('data/x.sqlite3')"` creates the file; `git status` does not show `data/`

**Dependencies:** none (commit the tracing change first)
**Files:** `src/jarvis/db.py`, `src/jarvis/config.py`, `tests/test_db.py`, `README.md`, `.gitignore`
**Scope:** S

### Task 17: Saved history across restarts ✅
**Description:** `History(path)` saves each turn as JSON and loads the newest ones that are less than 12 hours old. `Brain` takes `history=`, loads at start and saves after each turn, except turns using `FORGOTTEN_TOOLS` (not kept at all) and `UNSAVED_TOOLS = {"web_lookup"}` (kept for this run, never written). A failing load or save prints one line and never breaks `ask`. `app.main` wires it in unless `DB_FILE` is `None`.

**Acceptance criteria:**
- [x] Round-trip keeps Indonesian text and tool-call messages; oldest first; `limit`, the 12-hour cut, pruning to `keep=100` and a skipped corrupt row are all tested
- [x] A `web_lookup` turn stays in `brain.history` but is not in the database; a clock turn is in neither; a raising `load`/`save` does not break `ask`
- [x] Manual (typed, English and Indonesian): chat, exit, restart, then "what did I ask you before?" is answered from the saved turns

**Verification:**
- [x] `uv run pytest -q tests/test_history.py tests/test_brain.py tests/test_app.py`, then the full suite and ruff
- [x] `uv run python scripts/check_conversation.py 3` still reads 75/75 and 75/75
- [x] Manual: the restart check above

**Dependencies:** 16
**Files:** `src/jarvis/history.py`, `src/jarvis/brain.py`, `src/jarvis/app.py`, `tests/test_history.py`, `tests/test_brain.py`, `SPEC.md`
**Scope:** M

### Task 18: Facts store and the remember/forget tools ✅
**Description:** `Facts(path)` with `all`, `add` and `remove`, plus the rules: 3-200 characters, at most 30 facts, a 3-character minimum for `remove`, and `looks_secret`. `memory_tools.build(facts)` returns `remember` and `forget`, both `refused_after=frozenset({"web_lookup"})`. `Tool` gets `refused_after`; `_converse`/`_execute` know where the current turn starts and refuse those tools after `web_lookup` in the same turn. The tools are merged in `app.main`. This task runs the tool-choice check before the prompt changes, because a new tool has shifted older behaviour every time so far.

**Acceptance criteria:**
- [x] Unit tests cover every `Facts` rule and every `looks_secret` case ("pin" inside another word is allowed), and every result string of both tools
- [x] In a turn that called `web_lookup`, both tools return `error: not allowed in a turn that read web content` and the database does not change; in other turns they run
- [x] `check_tools.py` has `remember`/`forget` cases in both languages and negative cases that call nothing ("how do I remember a password", "what is RAM", "how do I forget a wifi network", plain chat); `check_tools.py 3` reads `wrong: 0 of <new total>` twice

**Verification:**
- [x] `uv run pytest -q tests/test_facts.py tests/test_memory_tools.py tests/test_brain.py`, then the full suite and ruff
- [x] `PYTHONIOENCODING=utf-8 uv run python scripts/check_tools.py 3`, run twice
- [x] Manual (typed): "remember that my cat is called Mochi", then "remember my password is hunter2" (refused), then "forget the cat"

**Dependencies:** 17
**Files:** `src/jarvis/facts.py`, `src/jarvis/memory_tools.py`, `src/jarvis/tools.py`, `src/jarvis/brain.py`, `src/jarvis/app.py`, `tests/test_facts.py`, `tests/test_memory_tools.py`, `scripts/check_tools.py`
**Scope:** M (more files than the 5-file guide, but most are small and new)

**Result:** 365 tests (308 before), ruff clean; `check_tools.py 3` wrong 0 of 126 on the final wording, twice in the final check (4 more clean runs while tuning); `check_conversation.py 3` fresh data 75/75, reply language 75/75. Manual typed run: the cat fact was stored, the password was refused, "forget the cat" emptied the table.
**Found on the way:** with remember/forget added, "berita terbaru hari ini apa?" (and once "what's the news today?") called `get_datetime` before `web_lookup`, 3 of 126 in 3 of 5 runs (baseline 0 of 84 in 5 runs). Shortening the new descriptions made it worse (6 of 126 every run); adding "the news is not a date question, so never check the date first" to the `web_lookup` description fixed it (0 of 126 in 6 runs).

### Task 19: Facts shown to the model ✅
**Description:** `Brain(facts=...)` takes a callable. `_system_prompt(lang, facts)` puts the labelled facts block before `SYSTEM_PROMPT` so the language sentence stays last. With no facts the prompt is byte-identical to today's. `app.main` passes `facts=facts.all`.
**Decided 2026-10-18 (user):** add `remember` and `forget` to `FORGOTTEN_TOOLS`, so those turns are kept neither in memory nor on disk. Otherwise the old "remember ..." turn still shows a forgotten fact for up to 12 hours (spec success criterion 3). The facts block is then the only place a fact lives. Add a test: after remember then forget, neither `brain.history` nor the store holds the fact.
**Decided 2026-10-18 (user), after the manual check failed:** a successful forget also clears the conversation history (memory and disk).
**From Task 18:** `check_tools.py 3` flips between runs at temperature 0 ("news today" calling `get_datetime` first), so run it at least 4 times, not twice.

**Acceptance criteria:**
- [x] A test shows the no-facts prompt equals the old prompt exactly, and with facts the block comes first and the prompt still ends with the language sentence
- [x] `check_conversation.py` has a multi-turn case with 3 stored facts (1 Indonesian, 2 English): questions about each are answered from the facts with no tool call and in the question's language, and unrelated questions do not mention them. `check_conversation.py 3` still reads 75/75 and 75/75
- [x] Manual: "remember that my cat is called Mochi", restart, then "what is my cat called?" is answered correctly, in English and in Indonesian. With 30 facts, the time to the first reply is no more than 0.3 s slower (from `logs/trace.jsonl`)

**Verification:**
- [x] `uv run pytest -q tests/test_brain.py`, then the full suite and ruff
- [x] `PYTHONIOENCODING=utf-8 uv run python scripts/check_conversation.py 3` and `check_tools.py 3`, each run twice
- [x] Manual: the Mochi restart check and the latency comparison

**Dependencies:** 18
**Files:** `src/jarvis/brain.py`, `src/jarvis/app.py`, `tests/test_brain.py`, `scripts/check_conversation.py`, `SPEC.md`
**Scope:** S

**Result:** 370 tests pass; ruff clean. `check_conversation.py 3`, 3 runs, each: `fresh data 75/75, reply language 75/75` / `with facts: fresh data 75/75, reply language 75/75` / `facts: right 18/18, reply language 27/27, unrelated clean 9/9` (the first, label-only run read `facts: right 16/18`: the model called `remember` on "what kind of shifts do I work?"; fixed by adding "answer questions about it without calling a tool" to the label). `check_tools.py 3` x4: `wrong: 0 of 126` each time. Latency (timing `Brain.ask` directly, "how are you?", 7 alternating runs): median 0.394 s with no facts, 0.535 s with 30 facts, +0.141 s. Manual (typed, throwaway database): remember, then in a new process "what is my cat called?" -> "Your cat is called Mochi.", "kucingku namanya siapa?" -> "Kucing Anda bernama Mochi." (both right). After "forget the cat" the facts table was empty, but "what is my cat called?" in a new process still answered "Your cat is still named Mochi.": the saved ordinary turns from run 2 ("what is my cat called?" / "Your cat is called Mochi.") are loaded from history. With the turns table emptied it said it did not know. The label cannot help because with no facts there is no block.
After the user's decision (a successful forget clears the history, `History.clear`, matched through `tool_call_id`): 376 tests pass, ruff clean. Manual, twice, throwaway database, one process per step: remember -> "I've remembered that your cat is called Mochi."; "what is my cat called?" -> "Your cat is called Mochi.", "kucingku namanya siapa?" -> "Kucing Anda bernama Mochi."; "forget the cat" -> "I have forgotten your cat's name." (second run: "I have forgotten that your cat is named Mochi."), then `facts` 0 rows and `turns` 0 rows; new process "what is my cat called?" -> "I don't know the name of your cat. I can only remember facts you explicitly ask me to store." both times. No prompt or tool description changed, so check_tools/check_conversation were not rerun.

### Task 20: `--reset-memory` and the memory docs ✅
**Description:** `uv run jarvis --reset-memory` asks `Delete all remembered facts and saved history? [y/N]` (via `is_yes`), empties both tables only after a clear yes, prints the result and exits without loading any model. Also: the README Safety section (what is stored, in plain text, only on this PC, and how to wipe it), the SPEC.md sections for `history`, `facts`, `memory_tools` and the prompt-injection rules, and the CLAUDE.md architecture notes.

**Acceptance criteria:**
- [x] A "y" empties both tables; "n", an empty answer or anything unclear changes nothing; no model, client or audio is loaded (test_app)
- [x] With `config.DB_FILE = None`, no file is created and no memory tool is offered (test_app)
- [x] README, SPEC.md and CLAUDE.md match the code: every new module, setting and command is named, and nothing is documented that the code does not do

**Verification:**
- [x] `uv run pytest -q tests/test_app.py tests/test_readme.py`, then the full suite and ruff
- [x] Manual: `uv run jarvis --reset-memory`, answer `n` (data stays), run again and answer `y` (both tables empty); `JARVIS_DB_FILE=off uv run jarvis --no-voice` creates no file

**Dependencies:** 19
**Files:** `src/jarvis/app.py`, `src/jarvis/facts.py`, `src/jarvis/history.py`, `tests/test_app.py`, `tests/test_facts.py`, `tests/test_history.py`, `README.md`, `SPEC.md`, `CLAUDE.md`, `docs/SPEC-memory.md`
**Scope:** S

**Result:** 388 tests (376 before), ruff check and format clean. `reset_memory()` in `app.py` runs right after `parse_args`; `Facts.clear()` is new and `History.clear()` now returns its row count, so the message can say how many were deleted. Manual with a throwaway database (2 facts, 3 turns): `n` -> "Nothing was deleted." and the counts stayed 2 and 3; `y` -> "Deleted 2 facts and 3 saved turns." and both counts 0; a missing file was not created; `JARVIS_DB_FILE=off` printed that memory is off; `JARVIS_DB_FILE=off` with `--no-voice` and "exit" created no file. No prompt or tool description changed, so the real-model checks were not rerun. README, SPEC.md, CLAUDE.md and docs/SPEC-memory.md updated; README's "no memory between runs" and "cannot make Jarvis do anything" lines were wrong and are fixed.

### Task 21: Private-address guard for `web_lookup page` ✅ (the spoken refusal through the full Jarvis loop is left to the user)
**Description:** `netguard.check_public(url)` resolves the host and raises `BlockedAddress` if any resolved address is not `is_global` (IPv4-mapped IPv6 is unwrapped first). A name that does not resolve is not reported as blocked. `GuardedRedirectHandler` checks every redirect target. `web.page()` checks first and fetches through the guarded opener; `news`/`wiki` are unchanged. SPEC.md: the Limits line is reversed with the reason, and DNS rebinding is written down as the known residual risk.

**Acceptance criteria:**
- [x] With `socket.getaddrinfo` patched: `127.0.0.1`, `10.x`, `172.16.x`, `192.168.x`, `169.254.169.254`, `100.64.x`, `::1`, `fc00::1`, `::ffff:127.0.0.1` and a name with one public and one private address are blocked; a public address is allowed; an unresolvable name is not blocked
- [x] A redirect to a private address is refused and one to a public address is followed; `page()` returns `error: could not read that page (blocked: that address is on a private network). Tell the user so and call no more tools.`; `web.py` still does not import `browser`
- [ ] Manual: `web_lookup page` on `http://127.0.0.1:11435/v1/models` is refused with a spoken reason; a news page and Wikipedia still work; a public URL that redirects to a local `127.0.0.1` test server is refused

**Verification:**
- [x] `uv run pytest -q tests/test_netguard.py tests/test_web.py`, then the full suite and ruff
- [x] `PYTHONIOENCODING=utf-8 uv run python scripts/check_tools.py 3` still reads `wrong: 0 of 84` (no description changed; this confirms nothing shifted)
- [ ] Manual: the three checks above

**Result:** 308 tests, ruff clean; `check_tools.py 3` wrong 0 of 84. Real calls: `web_lookup page` on `127.0.0.1:11435/v1/models` and `192.168.1.1` returned the blocked error; news, Wikipedia and a Wikipedia page still answered. Redirect: a real 302 between two `127.0.0.1` servers was refused by the real `GuardedRedirectHandler` (plain urllib followed it). Not checked: a real public URL redirecting to a private one, and the refusal spoken through `uv run jarvis`.
**Dependencies:** none (parallel with 16)
**Files:** `src/jarvis/netguard.py`, `src/jarvis/web.py`, `tests/test_netguard.py`, `tests/test_web.py`, `SPEC.md`
**Scope:** M

### Task 22: Web-content guard also covers the kept history ✅ (the real-model checks are left to the user)
**Description:** Review of Tasks 16-21 found that `refused_after` looked only at the current turn. A `web_lookup` turn stays in the in-memory history (it is only kept off the disk), so the page's text was still in front of the model on the next turn, where `remember` was allowed. Demonstrated with the real `Brain`, `Facts` and `History`: turn 1 `web_lookup`, turn 2 an unrelated question, and the model's `remember` call stored the fact. `_converse` now passes `_tools_used(messages)` (system prompt, kept turns and this turn) instead of `messages[start:]`, and the `start` parameter is gone. The refusal text is now `error: not allowed after web content was read in this conversation`, because "in a turn" would be wrong for a later turn.

**Acceptance criteria:**
- [x] `remember` and `forget` are refused in the turn after a `web_lookup` turn (the old test that pinned the opposite is replaced)
- [x] They work again once the web turn has left the last 10 turns, and after a restart (the web turn was never saved)
- [x] A conversation with no `web_lookup` is never blocked
- [x] The new "refused in the next turn" test fails on the old behaviour and passes now

**Verification:**
- [x] `uv run pytest -q`, `uv run ruff check src tests scripts`, `uv run ruff format --check src tests scripts`
- [ ] Manual: `"what is the news?"`, then `"remember that I like jazz"` is refused in speech; after 10 more turns, or a restart, the same request is stored
- [ ] `check_tools.py 3` still `wrong: 0 of 126`, and `check_conversation.py 3` still 75/75 and 75/75 (no prompt or description changed; this confirms the refusal text did not shift anything)

**Dependencies:** 19
**Files:** `src/jarvis/brain.py`, `tests/test_brain.py`, `SPEC.md`, `CLAUDE.md`, `docs/SPEC-memory.md`, `tasks/plan.md`
**Scope:** S

## Checkpoint: Memory and web guard complete
- [ ] All 9 success criteria in `docs/SPEC-memory.md` pass
  - 7 of 9 met. #4 (Indonesian secret) was closed 2026-10-18 with the real model: "kata sandi wifi", a 16-digit KTP number and "PIN ATM", 2 runs each, all refused in Indonesian, nothing stored. Still partly met: #5 (unit tests only, no real injected page) and #7 (no real public-to-private redirect, refusal not heard through `uv run jarvis`).
- [x] `check_tools.py 3` 0 wrong and `check_conversation.py 3` 75/75 and 75/75, each repeated (Task 19 Result: `check_tools.py 3` x4 wrong 0 of 126, `check_conversation.py 3` 3 runs; nothing since changed a prompt or description)
- [ ] Human review
