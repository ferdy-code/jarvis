# Implementation Plan: Jarvis MVP

Source: [SPEC.md](../SPEC.md) (approved 2026-10-10) · Tasks: [todo.md](todo.md)

## Overview

We build Jarvis in three phases. Each phase ends with something you can actually use.

1. **Typed Jarvis:** chat plus all the system actions, in the terminal.
2. **Speaking Jarvis:** replies are spoken through Supertonic 3.
3. **Listening Jarvis:** "Hey Jarvis" wake word, then Whisper speech recognition, giving the full voice loop.

The riskiest unknown, whether the voice packages install on Python 3.14, gets settled in Task 1, before any feature code exists.

## Dependency Graph

```
config ──► brain ──► app (typed loop) ──► app (voice thread)
             ▲                              ▲    ▲    ▲
tools ───────┘                              │    │    │
                                   tts ─────┘    │    │
                                   stt ──────────┘    │
                                   wake ──────────────┘
```

`tools`, `tts`, `stt` and `wake` don't depend on each other. Only `app` connects them.

## Architecture Decisions

- **Install every dependency in Task 1** instead of adding them when needed. If something fails on Python 3.14, we find out now and fall back to 3.12, before any code depends on the version.
- **Slice by user-visible behaviour, not by module.** Task 3 adds the tool loop *and* the first two tools, because a tool loop with no tools can't be checked by hand.
- **`brain` takes `confirm` as a callback,** so the dangerous-action logic is unit-tested with no terminal or microphone. `app` supplies the terminal y/n version (Task 5) and the voice yes/ya version (Task 9).
- **Heavy imports happen lazily** (inside the loader functions), so the typed phase and the tests don't need audio hardware.
- **One commit per task** after `pytest` + `ruff` pass. The repo has no commits yet, so Task 1 makes the first one (on a new `main` branch, which matches the configured main branch).

## Task List

### Phase 1: Typed Jarvis
- [x] Task 1: Install dependencies and dev tooling (fail-fast on Python 3.14)
- [x] Task 2: Typed chat end to end (config + brain + app, no tools)
- [x] Task 3: Time and battery answers (tool loop + first tools)
- [x] Task 4: Volume control and lock
- [x] Task 5: Shutdown and restart with confirmation

### Checkpoint A: Typed Jarvis is usable every day
- [x] SPEC success criteria 1–5 and 9 pass
- [ ] Human review

### Phase 2: Speaking Jarvis
- [x] Task 6: Spoken replies with Supertonic 3 (en + id)

### Checkpoint B: Jarvis talks
- [ ] Typed questions get spoken answers in the right language; `--no-voice` still works
- [ ] Human review (voice choice)

### Phase 3: Listening Jarvis
- [x] Task 7: Speech-to-text with faster-whisper (smoke script)
- [x] Task 8: Wake-word detector (smoke script)
- [x] Task 9: Full voice loop in the app
- [ ] Task 10: README usage docs

### Checkpoint C: MVP complete
- [ ] All 9 SPEC success criteria pass
- [ ] Human review

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| No Python 3.14 wheel for `ctranslate2`, `onnxruntime` or `openwakeword` on Windows | High | Task 1 imports each package. Fall back to 3.12 and update SPEC |
| The 4B model calls the wrong tool or invents an action | Med | Strict tool descriptions, a system prompt rule, and manual Indonesian/English checks in Tasks 3–5. Try `Qwen3-8B` if it's bad |
| Whisper + Qwen + KV cache go over 8 GB of VRAM | Med | Whisper `small` float16 is about 1 GB. If out of memory, use `int8_float16` or run Whisper on the CPU |
| False wake-word triggers in daily use | Med | Configurable threshold, tuned in Task 8 against SPEC criterion 8 |
| Microphone contention between wake and stt | Low | They run one after the other in the same thread, never at once |
| pycaw API differs between versions | Low | Wrap it in one function and test it with a fake |
| Supertonic Indonesian quality is poor | Low | Try other presets in Task 6. The user already chose this engine |

## Parallelization

Tasks 6, 7 and 8 are independent once Task 2 is done. They're kept sequential because this is a single-person learning project and each one needs a manual audio check.

## Open Questions (from SPEC, resolved during tasks)

- Supertonic voice (male or female, which preset): Task 6
- Whisper `small` vs `medium` for Indonesian: Task 7
- Python 3.14 vs 3.12: Task 1
