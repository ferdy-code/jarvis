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
- History is in memory only, trimmed to the last 20 messages, and lost on exit.
- If the LLM server can't be reached, it returns the message "My brain is offline. Is LlamaStash running?" and doesn't crash.

### `tts`

- `speak(text: str, lang: str) -> None` uses Supertonic `TTS(auto_download=True)` with a preset voice (default `M1`, configurable), and plays the audio through `sounddevice`. It blocks until playback finishes.
- `lang` must be `en` or `id`. Anything else falls back to `en`.
- The model is loaded once and stays in memory. Voices: `M1`-`M5`, `F1`-`F5`; output is 44.1 kHz. First run downloads about 385 MB to `~/.cache/supertonic3`.
- For `id`, numbers are spelled out as Indonesian words before synthesis (`spell_numbers_id`). Supertonic misreads Indonesian digits ("85 persen" was heard as "25%", "18:15" as "12.15"); written as words they were heard correctly 8 times out of 8. English digits are read fine.
- `guess_lang(reply)` picks `en` or `id` for typed turns by counting function words in the reply. Voice turns will use the language Whisper detected.

### `stt`

- `listen() -> tuple[str, str]` records from the default microphone at 16 kHz mono. It stops after 1.0 s of silence (energy threshold) or 15 s total, then runs `faster-whisper` (`small`, `cuda`, `float16`).
- It returns `(text, lang)`. If Whisper detects a language other than `en` or `id`, `lang` is set to `en`.
- It returns `("", lang)` when nothing was said.

### `wake`

- `wait_for_wake_word() -> None` streams the microphone in 80 ms chunks into openWakeWord's `hey_jarvis` model and returns when the score is ≥ 0.5 (threshold configurable).
- It shares the microphone with `stt` one after the other, never at the same time (wake → stt → back to wake).

### `app`

- `uv run jarvis` starts typed input plus voice. `uv run jarvis --no-voice` starts typed input only.
- **Main thread:** reads typed lines. `exit` or `quit` stops Jarvis.
- **Voice thread (daemon):** loops wake → beep → `stt.listen()` → `brain.ask()` → print + `tts.speak()`.
- One lock around `brain.ask` + `speak`, so typed and voice turns never overlap.
- **Language:** voice turns use Whisper's language. Typed turns reuse the last detected language (English to start).
- **Confirm:** a typed turn asks `y/n` on the terminal. A voice turn speaks the question, then `stt.listen()` and accepts `yes`/`ya`/`iya`. Anything else counts as no.
- **Graceful degradation:** if the microphone, Whisper, or the wake model fails to load, Jarvis prints a warning and runs typed-only. If TTS fails to load, it prints text only. It only exits on `exit` or Ctrl+C.

### Config (`config.py`)

Plain module-level constants, read once from environment variables with defaults. No config file.

| Env var | Default |
|---|---|
| `JARVIS_BASE_URL` | `http://127.0.0.1:11435/v1` |
| `JARVIS_MODEL` | `Qwen3.5-4B-Q4_K_M` |
| `JARVIS_API_KEY` | `llamastash` (stub, ignored by the loopback proxy) |
| `JARVIS_WHISPER_MODEL` | `small` |
| `JARVIS_VOICE` | `M1` |
| `JARVIS_WAKE_THRESHOLD` | `0.5` |

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

1. **Supertonic voice:** `M1` is the only preset name confirmed so far. Should Jarvis sound male or female? I'll list the available presets when building `tts`.
2. **Whisper size:** `small` is the starting point. If Indonesian accuracy is poor, try `medium` (more VRAM, slower). This gets decided after the smoke test.
3. ~~**Python 3.14 wheels**~~ **Resolved (Task 1):** every dependency installs and imports on Python 3.14, so no fallback is needed. `ctranslate2` sees the GPU (CUDA, float16 supported). `onnxruntime` is CPU-only, which is fine for the wake word.
4. **Wake-word chime:** a short beep after "hey jarvis" so you know it's listening. I've assumed yes, using a generated tone with no audio file.
