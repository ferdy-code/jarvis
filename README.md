# Jarvis

A personal assistant for your Windows PC that you can type to or talk to, in English or
Indonesian. Say "Hey Jarvis" and a command, and it answers out loud. The language model,
speech recognition and voice all run on your own machine, so chatting and controlling the PC
work offline and cost nothing. Only playing music and the web summaries need the internet.

## What it can do

- Answer questions and chat.
- Tell you the date, time and battery level.
- Change the volume (up, down, mute, unmute) and lock the screen.
- Turn the screen on when it is off ("wake up the screen", "nyalakan layar").
- Play a song on YouTube Music ("putar lagu Tulus Hati-Hati di Jalan", "play Yellow by Coldplay"). A new request pauses the old song and opens the new one in a new Firefox tab.
- Read the web and answer out loud, naming the source: the news ("berita hari ini apa?", "any news about Indonesia's economy?") from Google News, facts ("look it up on the internet: who is Tulus?") from Wikipedia, and a summary of a website you name ("summarize bbc.com", "rangkum isi kompas.com"). Nothing is opened on screen.
- Shut down or restart the PC, but only after you say yes.

```
you> what time is it?
jarvis> It is Saturday 10 October 2026, 19:58.

you (voice)> kecilkan volume
jarvis> Volume telah dikurangi menjadi 90%.

you (voice)> restart the PC
jarvis> Do you want me to run power action restart? Say yes or no.
you (voice)> tidak
jarvis> The restart was cancelled by the user.
```

## What you need

- Windows 11 and [uv](https://docs.astral.sh/uv/) (it installs Python 3.14 for you).
- LlamaStash with the `Qwen3.5-4B-Q4_K_M` model loaded and its proxy running on port
  11435. `llamastash status` shows what is running. Another server that speaks the OpenAI
  API should work too (see [Settings](#settings)), but only LlamaStash has been tried.
- A microphone and speakers.
- An NVIDIA GPU is recommended. Speech recognition takes 0.13 s per phrase on it and
  2.7 s on the CPU, which Jarvis falls back to by itself. The GPU needs about 400 MB of
  free memory next to the language model.

## Install and run

```
uv sync
uv run jarvis
```

The first run downloads the voice (385 MB) and the speech-recognition model, and on an
RTX 50-series GPU it spends about 25 seconds compiling GPU code once. Later starts take
about 6 seconds and print `Loading the voice and listening models`.

When you see `Jarvis is ready`, either type at `you>` or say **"Hey Jarvis"**. The
terminal prints `(wake word heard - speak now)` and a short beep plays; then say your
command. Jarvis stops listening after a second of silence.

| Command | What it does |
|---|---|
| `uv run jarvis` | Typing and voice, replies printed and spoken |
| `uv run jarvis --no-voice` | Typing only, nothing spoken, starts in a second |
| `exit` or `quit` | Leave (Ctrl+C works too) |

`python` is not on the PATH on a stock Windows install, so run everything through `uv run`.

## Settings

All settings are environment variables, and all are optional. In PowerShell:
`$env:JARVIS_VOICE = "F1"; uv run jarvis`.

| Variable | Default | Meaning |
|---|---|---|
| `JARVIS_BASE_URL` | `http://127.0.0.1:11435/v1` | OpenAI-compatible server |
| `JARVIS_MODEL` | `Qwen3.5-4B-Q4_K_M` | Model name on that server |
| `JARVIS_API_KEY` | `llamastash` | API key (LlamaStash ignores it) |
| `JARVIS_VOICE` | `M2` | Speaking voice: `M1`-`M5` or `F1`-`F5` |
| `JARVIS_WHISPER_MODEL` | `small` | Speech-recognition model size |
| `JARVIS_MIC_THRESHOLD` | `0.003` | Loudness that counts as speech (0 to 1) |
| `JARVIS_WAKE_THRESHOLD` | `0.5` | How sure the wake word must be (0 to 1) |
| `JARVIS_FIREFOX_PROFILE` | `Keina Nara` | Firefox profile that pages open in, by the name Firefox shows. Empty means the default browser |
| `JARVIS_TRACE_FILE` | `logs/trace.jsonl` | Where the trace of each turn is appended. `off` turns tracing off |
| `JARVIS_DB_FILE` | `data/jarvis.sqlite3` | Where the conversation history and remembered facts are kept. `off` turns memory off |

To use OpenAI instead of the local model, set `JARVIS_BASE_URL=https://api.openai.com/v1`,
`JARVIS_MODEL` and `JARVIS_API_KEY`. For a non-local address Jarvis stops sending the
llama.cpp-only options and keeps the normal retries. This has not been tried against
OpenAI itself, and the system prompt was tuned for the small local model.

## Safety

- Jarvis can only run the fixed list of actions above. It never runs commands the model
  writes.
- Shutdown and restart ask first: `[y/N]` for typed requests, a spoken question for voice
  requests. Only "y", "yes", "yeah", "ya" or "iya" count. Anything else, including
  silence, cancels.
- Microphone audio is only kept in memory while it is processed, never written to disk.
- Each turn is traced to a file on your PC: what you said and Jarvis replied, the tools it
  ran with their results (cut to 200 characters), and how long each step took. Delete the
  file whenever you like, or turn tracing off in Settings. It is not sent anywhere.
- Your conversation stays on your PC unless you point `JARVIS_BASE_URL` somewhere else. The
  only things sent out are the song name you ask for (to YouTube Music, to find it), the
  topic or address of a web request (to Google News, Wikipedia or that site), and the pages
  Firefox loads for music. The text of a web page goes only to your local model.

## Troubleshooting

| What you see | What to do |
|---|---|
| `... no sound started ... Firefox may be blocking autoplay` | Firefox does not let a page play sound until it is allowed. In the Firefox profile Jarvis uses, open a `music.youtube.com` page, click the icon at the left end of the address bar, and under Permissions > Autoplay choose Allow Audio and Video. |
| `My brain is offline. Is LlamaStash running?` | Start LlamaStash and load the model. `llamastash status` should list it. |
| `Voice is off (...)` | The voice could not load. Typing still works. Check the message, for example a wrong `JARVIS_VOICE`. |
| `Voice input is off (...)` | The microphone, Whisper or the wake word failed to load. Typing still works. |
| `Whisper GPU unavailable ... Using the slower CPU` | Works, but each command takes about 3 s longer. Check that your NVIDIA driver is installed. |
| It never reacts to "Hey Jarvis" | Run `uv run python scripts/smoke_audio.py wake` and say it. Lower `JARVIS_WAKE_THRESHOLD` (try 0.3) if nothing prints. |
| "Wake word heard" but then "heard nothing" | Your voice is too quiet for the threshold. Run `uv run python scripts/smoke_audio.py mic`, speak, and set `JARVIS_MIC_THRESHOLD` to about a third of the level it shows. |
| It wakes by itself | Raise `JARVIS_WAKE_THRESHOLD` (try 0.7). Saying "Jarvis" in any sentence can wake it. |
| It understood the wrong words | The recognised text is always printed as `you (voice)> ...`. Say it again, a little slower. |

## Limits

- Every song opens a new Firefox tab, so tabs pile up until you close them.
- Playing music needs autoplay allowed for `music.youtube.com` (see Troubleshooting) and the
  internet.
- Web summaries use only plain page text: sites that need JavaScript, a login or block
  programs (many news sites answer 401 or 403) get "could not read that page". Jarvis
  reads the first 4000 characters, so it summarises the top of a page, not all of it. A
  page can make the summary wrong, but it cannot make Jarvis do anything.
- Whisper sometimes mishears one- or two-word commands, and writes "computer" for
  "komputer", so Jarvis may then answer in English.
- Answers and actions depend on a small 4B model. After a time question it may answer a
  meaningless fragment with the time again.
- Jarvis can wake a screen that is off, but it cannot unlock a locked PC: Windows does
  not allow a normal program to do that. You sign in yourself (PIN, Windows Hello, or
  Windows Voice Access, which can speak your PIN on the sign-in screen). It cannot turn the
  screen off either.
- If the whole PC is asleep, not just the screen, Windows suspends Jarvis and it cannot hear
  you. Untested: with the PC locked Jarvis should keep listening, which means anyone nearby
  could talk to it, including answering yes to a shutdown question.
- Windows only, one user, no memory between runs.

## Development

```
uv run pytest -q                              # unit tests, no audio or model needed
uv run ruff check src tests scripts           # lint
uv run ruff format src tests scripts          # format
uv run python scripts/check_conversation.py   # multi-turn check on the real model
uv run python scripts/smoke_audio.py mic      # also: stt, wake, tts [voices | all]
```

Run `check_conversation.py` after changing the system prompt or a tool description: the
wording matters a lot to the small model, and unit tests cannot see it.

```
src/jarvis/app.py     typing and voice loop, confirmations
src/jarvis/brain.py   conversation with the model, runs the tool calls
src/jarvis/tools.py   the actions Jarvis can take
src/jarvis/web.py     news, Wikipedia and page summaries (plain urllib, no browser)
src/jarvis/stt.py     microphone recording and Whisper
src/jarvis/wake.py    "Hey Jarvis" detection
src/jarvis/tts.py     Supertonic voice
src/jarvis/mic.py     the shared microphone stream
src/jarvis/config.py  settings
```

The design, the measurements behind it and the task history are in [SPEC.md](SPEC.md)
and [tasks/](tasks/).
