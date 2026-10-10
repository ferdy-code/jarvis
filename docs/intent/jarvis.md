# Jarvis: Statement of Intent

Confirmed 2026-10-10.

- **Outcome:** Jarvis is a Python assistant that runs in the terminal on your Windows PC. You can type to it, or say "Hey Jarvis" and speak. It answers in text and out loud.
- **What it does (MVP):**
  1. Answers questions and chats.
  2. Handles system info and control: time and date, battery, volume (up, down, mute), lock, and shutdown or restart (shutdown and restart ask for confirmation first).
- **Brain:** a local LLM through LlamaStash (llama.cpp), using its OpenAI-compatible API at `http://127.0.0.1:11435/v1`. The model is `Qwen3.5-4B-Q4_K_M`, with `Qwen3-8B` available as a fallback. Switching to OpenAI later only means changing the config.
- **Voice:**
  - Wake word: openWakeWord "hey jarvis".
  - Speech to text: local Whisper, which detects English or Indonesian automatically.
  - Text to speech: Supertonic 3 (`pip install supertonic`, runs on the CPU, supports `en` and `id`), replying in the same language you spoke.
  - Everything runs offline.
- **User:** just you, on this PC (Windows 11, RTX 5060 8 GB, 16 GB RAM).
- **Why:** it's a learning project, but you want to use it every day. So the code should be simple and easy to read, and it also has to be reliable enough to leave running.
- **Success:** "Hey Jarvis, what time is it?" or "Hey Jarvis, kecilkan volume" gets the right action plus a spoken answer within a few seconds, with no internet.
- **Constraint:** it must run locally and be free to use, and swapping the LLM provider must stay easy.
- **Out of scope (MVP):**
  - Opening or closing apps and websites
  - Google Calendar and Gmail
  - A GUI window
  - Memory across sessions
  - Cloud APIs
  - Running on other PCs

## Verified facts

- LlamaStash proxy at `127.0.0.1:11435`. `/v1/models` lists `Qwen3.5-4B-Q4_K_M` and `Qwen_Qwen3-8B-Q4_K_M`.
- Tool-calling test: the prompt "Kecilkan volume" produced `set_volume(direction="down")` in about 1.5 s, at about 80 tokens per second.
- Qwen3.5 returns a `reasoning_content` (thinking) step before answering, which adds latency. Consider turning thinking off for quick commands.
