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
- [x] Task 10: README usage docs

### Checkpoint C: MVP complete
- [x] All 9 SPEC success criteria pass
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

---

# Implementation Plan: Memory and Web Guard

Source: [docs/SPEC-memory.md](../docs/SPEC-memory.md) (draft 2026-10-18) · Tasks: [todo.md](todo.md#memory-and-web-guard) (Tasks 16-21)

## Overview

Three parts, each one usable by itself: **A** saves the last turns so they survive a restart, **B** adds explicit "remember / forget" facts that are shown to the model in every prompt, and **C** stops `web_lookup page` from fetching private-network addresses, including through redirects. Everything uses the standard library. `JARVIS_DB_FILE=off` gives exactly today's behaviour.

## Dependency Graph

```
db.py + config.DB_FILE (16) ──► history.py + Brain(history) (17) ──► facts.py + memory tools (18) ──► facts in prompt (19) ──► --reset-memory + docs (20)

netguard.py + web.page (21)        independent; may run in parallel with 16
```

## Architecture Decisions

- **Numbering continues the existing list:** spec Task 1 = 16, 2 = 17, 3 = 18 + 19 (split, as the spec allows for L), 4 = 20, 5 = 21.
- **Spec Task 3 is split by risk, not by module.** Task 18 adds the two tools and their descriptions and runs `check_tools.py`. Every new tool has shifted older behaviour, so false `remember`/`forget` calls are the most likely failure and get found first. Task 19 then adds the facts block to the prompt and runs `check_conversation.py`, the multi-turn facts case and the latency check.
- **Each task updates its own docs** (Boundaries: "README, SPEC.md and CLAUDE.md in the same task"). Task 20 adds the reset command, the README Safety section and a final pass so the three documents match the code.
- **`brain.py` gets objects, not storage:** `history` (load/save) and `facts` (a callable). The unit tests use fakes and no sqlite.
- **`refused_after` needs the start of the current turn:** `ask` passes `start` to `_converse` and then to `_execute`, which checks `_tools_used(messages[start:])`.
- **One stop per task** so the user can run the real-model checks on this PC before the next one (spec "How to run this").

## Task List

### Prerequisite
- [ ] The uncommitted tracing change (`trace.py`, and edits to `app.py`, `brain.py`, `config.py`, `stt.py`, `tts.py`, tests, README) is committed. Then every task-worker commit holds only its own task's files.

### Phase A: Saved history
- [ ] Task 16: Database foundation (`db.py`, `JARVIS_DB_FILE`)
- [ ] Task 17: Saved history across restarts

### Checkpoint A
- [ ] `uv run pytest -q` and ruff pass; a restart keeps the conversation (typed, EN + ID)
- [ ] Human review

### Phase B: Remembered facts
- [ ] Task 18: Facts store and the remember/forget tools (tool choice checked)
- [ ] Task 19: Facts shown to the model (conversation checks, latency)
- [ ] Task 20: `--reset-memory` and the memory docs

### Checkpoint B
- [ ] `check_tools.py 3` reads `wrong: 0 of <total>`, `check_conversation.py 3` reads 75/75 and 75/75, each run twice
- [ ] Spec success criteria 1-6 and 8 pass
- [ ] Human review

### Phase C: Web guard (parallel with Phase A)
- [ ] Task 21: Private-address guard for `web_lookup page`

### Checkpoint: Complete
- [ ] All 9 spec success criteria pass
- [ ] Human review

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| `remember`/`forget` get called for ordinary questions ("how do I forget a wifi network"), or push older tools wrong again | High | Task 18 runs `check_tools.py` with negative cases before the prompt changes. Fallback (spec Open Question 4): drop `forget` as a tool |
| The facts block pulls the reply into the wrong language, or the model mentions facts when nobody asked | Med | Block goes before `SYSTEM_PROMPT`, language sentence stays last; Task 19 adds the multi-turn facts case |
| Saved turns carry stale tool results across a restart | Med | 12-hour age cut, clock/battery turns never saved; tune in daily use (Open Question 1) |
| Typed and voice threads write the database at once | Low | One connection per operation, and sqlite's file lock; `ask` is already behind the Brain lock |
| Parallel task-workers (16 and 21) commit over each other | Low | No shared files except possibly SPEC.md; each worker stages only its own files |
| DNS rebinding gets past the guard | Low | Accepted residual risk, written in SPEC.md (Task 21) |

## Open Questions

From the spec, unresolved: the 12-hour age (1), the 30 x 200 cap (2), and the possible `forget` fallback (4). Guard override (3): no setting, as recommended.
