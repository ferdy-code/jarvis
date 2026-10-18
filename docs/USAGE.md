# How to use Jarvis

Jarvis is an assistant for your Windows PC. You type to it or talk to it, in English or Indonesian (or a mix), and it answers out loud. It can chat, tell you the time, control the volume, play music and more.

## 1. Before you start

- LlamaStash must be running with the `Qwen3.5-4B-Q4_K_M` model loaded (check with `llamastash status`).
- A microphone and speakers for voice. Typing works without them.
- The internet for music and web summaries. Chat, time, battery, volume and lock work offline.
- For music: Firefox must allow autoplay for `music.youtube.com` in the "Keina Nara" profile (see [Troubleshooting](#7-troubleshooting)).

## 2. Start it

```
uv run jarvis              # typing and voice
uv run jarvis --no-voice   # typing only, starts in a second
```

`python` is not on your PATH, so always use `uv run`. After a code update, close the old Jarvis and start it again so it loads the new code.

The first start downloads the voice and speech models and can take a minute. Later starts take about 6 seconds. When you see **`Jarvis is ready`** you can use it.

## 3. How to talk to it

**Typing:** type at the `you>` prompt and press Enter.

**Voice:**
1. Say **"Hey Jarvis"**. You hear a short beep and the terminal prints `(wake word heard - speak now)`.
2. Say your command in one go, in English or Indonesian.
3. Stop talking. After about a second of silence Jarvis answers, out loud and in the terminal.

The recognised words are always printed as `you (voice)> ...`. If Jarvis misunderstood you, just say it again, a little slower.

Say **"exit"** or **"quit"** (typed), or press **Ctrl+C**, to leave.

Jarvis remembers the last 10 exchanges of the current run, so follow-ups work ("and now?", "yang tadi"). It forgets everything when you close it.

## 4. Everything Jarvis can do

| Tool | What it does | Say (English / Indonesian) |
|---|---|---|
| **Chat and questions** | Answers in 1 to 3 short sentences, in the language you used. No tool needed. | "Tell me a joke" / "Apa kabar?" / "How do I restart my computer?" (it explains, it does not do it) |
| **`get_datetime`** | Date, weekday and time | "What time is it?" / "Jam berapa sekarang?" / "Hari apa hari ini?" |
| **`get_battery`** | Battery percentage and charging state (a desktop PC says it has no battery) | "How much battery is left?" / "Baterai berapa persen?" |
| **`set_volume`** | Volume up, down, mute, unmute. Steps of 10% unless you say another amount | "Turn the volume up" / "Kecilkan volume" / "Mute" / "Unmute" / "Volume up by 30" |
| **`lock_pc`** | Locks the Windows screen | "Lock the PC" / "Kunci komputer" |
| **`wake_screen`** | Turns the screen on when it is off. It cannot unlock a locked PC: you sign in yourself | "Wake up the screen" / "Nyalakan layar" |
| **`play_music`** | Finds a song on YouTube Music and plays it in a new Firefox tab. Pauses whatever was playing. Says "playing ..." only when sound has really started | "Play Yellow by Coldplay" / "Putar lagu Tulus Hati-Hati di Jalan" |
| **`web_lookup`** | Reads the web and says a short summary out loud, naming the source. Three kinds: the **news** (Google News), an **encyclopedia** answer (Wikipedia, English or Indonesian) and a **website** you name by address. It opens nothing on screen | "What's the news today?" / "Berita hari ini apa?" / "Look it up on the internet: who is Tulus?" / "Cari di internet siapa itu Raisa" / "Summarize bbc.com" / "Rangkum isi kompas.com" |
| **`power`** | Shuts down or restarts the PC, after a 5 second countdown. **Always asks you first** | "Shut down the PC" / "Restart komputer" / "Matikan komputer" |

### Web summary tips

- Say a real address (`bbc.com`, `kompas.com`). A name without a dot, like "BBC", cannot be fetched.
- It reads the first 4000 characters of plain page text. Sites that need JavaScript or a login, or that refuse programs (401 or 403, common on news sites), get "could not read that page". It never guesses.
- A summary takes about 2 to 5 seconds. It uses no browser.

### Music tips

- Every new song opens a new Firefox tab. Close old ones yourself.

## 5. Safety: shutdown and restart

- Jarvis can only run the fixed actions in the table. It never runs commands the model makes up.
- Before `power` it always asks: `[y/N]` when you typed, and a spoken question when you used your voice. Only **y, yes, yeah, ya, iya** count as yes. Anything else, or silence, cancels.
- A greeting, "good night" or "thank you" is not a command.
- Your conversation stays on your PC. The only things sent out are the song name (to YouTube Music), the topic or address of a web request (to Google News, Wikipedia or that site) and the pages Firefox loads for music.
- Microphone audio is processed in memory and never written to disk.

## 6. Settings

All optional environment variables. In PowerShell: `$env:JARVIS_VOICE = "F1"; uv run jarvis`.

| Variable | Default | Meaning |
|---|---|---|
| `JARVIS_BASE_URL` | `http://127.0.0.1:11435/v1` | OpenAI-compatible server |
| `JARVIS_MODEL` | `Qwen3.5-4B-Q4_K_M` | Model name on that server |
| `JARVIS_API_KEY` | `llamastash` | API key (LlamaStash ignores it) |
| `JARVIS_VOICE` | `M2` | Speaking voice: `M1` to `M5` or `F1` to `F5` |
| `JARVIS_WHISPER_MODEL` | `small` | Speech-recognition model size |
| `JARVIS_MIC_THRESHOLD` | `0.003` | Loudness that counts as speech (0 to 1) |
| `JARVIS_WAKE_THRESHOLD` | `0.5` | How sure the wake word must be (0 to 1) |
| `JARVIS_FIREFOX_PROFILE` | `Keina Nara` | Firefox profile songs open in. Empty means the default browser |

To use OpenAI instead of the local model, set `JARVIS_BASE_URL=https://api.openai.com/v1`, `JARVIS_MODEL` and `JARVIS_API_KEY`. This has not been tried, and the prompt was tuned for the small local model.

## 7. Troubleshooting

| What you see | What to do |
|---|---|
| `My brain is offline. Is LlamaStash running?` | Start LlamaStash and load the model. |
| `... no sound started ... Firefox may be blocking autoplay` | In the Keina Nara profile open a `music.youtube.com` page, click the icon at the left end of the address bar, and under Permissions > Autoplay choose Allow Audio and Video. |
| `Voice is off (...)` | The voice failed to load. Typing still works. Read the message (for example a wrong `JARVIS_VOICE`). |
| `Voice input is off (...)` | The microphone, Whisper or the wake word failed to load. Typing still works. |
| `Whisper GPU unavailable ... Using the slower CPU` | It works but each command takes about 3 seconds longer. Check your NVIDIA driver. |
| It never reacts to "Hey Jarvis" | Run `uv run python scripts/smoke_audio.py wake` and say it. Lower `JARVIS_WAKE_THRESHOLD` (try 0.3). |
| "Wake word heard" but then "heard nothing" | Your voice is too quiet. Run `uv run python scripts/smoke_audio.py mic`, speak, and set `JARVIS_MIC_THRESHOLD` to about a third of the level shown. |
| It wakes by itself | Raise `JARVIS_WAKE_THRESHOLD` (try 0.7). |
| It understood the wrong words | Say it again, a little slower. Short one or two word commands are the most often misheard. |

## 8. Limits to know

- Windows only, one user, no memory between runs.
- Jarvis cannot unlock a locked PC or turn the screen off. If the whole PC sleeps, Jarvis cannot hear you.
- With the PC locked Jarvis should keep listening, so anyone nearby could talk to it, including answering yes to a shutdown question. This is untested.
- The answers depend on a small 4B model. It can occasionally pick the wrong action or answer in the wrong language.
- The song reply is spoken over the first seconds of the song.
- Whisper sometimes writes "computer" for "komputer", and Jarvis may then answer in English.

## 9. More documentation

- `README.md`: short overview and install.
- `SPEC.md`: the design, with the measurements behind each decision.
- `tasks/todo.md`: the history of each task and what real runs found.
