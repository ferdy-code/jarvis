import os
from urllib.parse import urlparse

BASE_URL = os.environ.get("JARVIS_BASE_URL", "http://127.0.0.1:11435/v1")
MODEL = os.environ.get("JARVIS_MODEL", "Qwen3.5-4B-Q4_K_M")
API_KEY = os.environ.get("JARVIS_API_KEY", "llamastash")
VOICE = os.environ.get("JARVIS_VOICE", "M2")
WHISPER_MODEL = os.environ.get("JARVIS_WHISPER_MODEL", "small")
# Loudness (0-1) a block of microphone audio must pass to count as speech. This
# room is 0.0001 when quiet, a voice at the mic peaks near 0.25, and a speaker
# across the room reaches 0.002.
MIC_THRESHOLD = float(os.environ.get("JARVIS_MIC_THRESHOLD", "0.003"))
WAKE_THRESHOLD = float(os.environ.get("JARVIS_WAKE_THRESHOLD", "0.5"))
# Pages open in this Firefox profile (the name Firefox shows). Without it, Windows
# hands a link to whichever profile answers first, which changes from one time to the next.
FIREFOX_PROFILE = os.environ.get("JARVIS_FIREFOX_PROFILE", "Keina Nara")
# One JSON line per turn (what was said, each model call and tool, how long each took).
# Windows cannot keep an empty variable, so "off" is how you turn it off there.
_trace_file = os.environ.get("JARVIS_TRACE_FILE", "logs/trace.jsonl")
TRACE_FILE = None if _trace_file.strip().lower() in {"", "off"} else _trace_file
# SQLite file holding the conversation history and remembered facts (plain text, this PC only).
# Windows cannot keep an empty variable, so "off" is how you turn it off there.
_db_file = os.environ.get("JARVIS_DB_FILE", "data/jarvis.sqlite3")
DB_FILE = None if _db_file.strip().lower() in {"", "off"} else _db_file

# Only llama.cpp gets these; a hosted API may reject them. Temperature 0 makes
# tool choice repeatable: at 0.7 the model sometimes asked to shut the PC down
# for "how do I shut down windows?" (3/8) and locked it on "goodnight" (4/8).
IS_LOCAL = urlparse(BASE_URL).hostname in {"127.0.0.1", "localhost"}
MAX_RETRIES = 0 if IS_LOCAL else 2  # retrying a dead local server only adds delay
EXTRA_BODY = (
    {"chat_template_kwargs": {"enable_thinking": False}, "temperature": 0}
    if IS_LOCAL
    else None
)
