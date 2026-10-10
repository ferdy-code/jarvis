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

### Task 7: Speech-to-text with faster-whisper
**Description:** `stt.listen()` records 16 kHz mono until 1.0 s of silence (or 15 s max), runs Whisper `small` on CUDA float16, and returns `(text, lang)`, with `lang` limited to `en` or `id`. Microphone audio is never written to disk.

**Acceptance criteria:**
- [ ] `scripts/smoke_audio.py stt`: saying "what time is it" prints `('what time is it', 'en')`. Saying "jam berapa sekarang" prints an `id` result
- [ ] Silence returns `("", lang)`. A recording longer than 15 s is cut off
- [ ] Transcription finishes in < 1.5 s after you stop speaking (most of the 4 s budget from SPEC criterion 6)

**Verification:**
- [ ] Smoke script, 5 EN + 5 ID phrases. Note the accuracy, then decide `small` vs `medium` (Open Question 2)
- [ ] `nvidia-smi` while Qwen and Whisper are both loaded: VRAM fits

**Dependencies:** Task 1
**Known problem (found in Task 6):** `WhisperModel(device="cuda")` loads but the first transcription fails with `Library cublas64_12.dll is not found`. Fix by installing the CUDA 12 runtime libraries (`nvidia-cublas-cu12`, maybe `nvidia-cudnn-cu12`) and making their DLLs findable, or use CPU `int8` (small: about 1-2 s per short clip; measure it). Also confirm the RTX 5060 is supported by ctranslate2's CUDA build.
**Files:** `src/jarvis/stt.py`, `scripts/smoke_audio.py`
**Scope:** S

---

### Task 8: Wake-word detector
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

### Task 9: Full voice loop in the app
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

### Task 10: README usage docs
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
- [ ] All 9 SPEC success criteria pass
- [ ] SPEC Open Questions answered and SPEC updated
- [ ] Human review
