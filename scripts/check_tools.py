"""Check that the real model picks the right tool for typical requests. Needs LlamaStash.

    uv run python scripts/check_tools.py [samples-per-phrase]

Run it after adding a tool or changing a tool description or the system prompt: every
new tool has shifted how the model treats older requests. Every tool is replaced by
a recorder that returns a canned result, so nothing really happens on the PC.
"""

import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from jarvis import config, memory_tools
from jarvis.app import openai
from jarvis.brain import Brain
from jarvis.facts import Facts
from jarvis.tools import TOOLS

SAMPLES = int(sys.argv[1]) if len(sys.argv) > 1 else 3

ANY = object()  # the argument must be given; its wording is not checked

# (phrase, expected tool or None for "no tool", expected arguments that must match)
CASES = [
    ("what's the news today?", "web_lookup", {"kind": "news", "language": "en"}),
    ("berita terbaru hari ini apa?", "web_lookup", {"kind": "news", "language": "id"}),
    ("any news about Indonesia's economy?", "web_lookup", {"kind": "news"}),
    ("ada kabar apa tentang MSCI Indonesia?", "web_lookup", {"kind": "news"}),
    ("look it up on the internet: who is Tulus?", "web_lookup", {"kind": "wiki"}),
    (
        "cari di internet siapa itu Raisa",
        "web_lookup",
        {"kind": "wiki", "language": "id"},
    ),
    ("search the web and tell me who built the Eiffel Tower", "web_lookup", {}),
    ("cari tahu di internet kapan Jakarta didirikan", "web_lookup", {"language": "id"}),
    ("summarize bbc.com for me", "web_lookup", {"kind": "page"}),
    (
        "rangkum isi kompas.com",
        "web_lookup",
        {"kind": "page", "language": "id"},
    ),
    ("what is on the front page of theverge.com?", "web_lookup", {"kind": "page"}),
    ("bacakan ringkasan situs detik.com", "web_lookup", {"kind": "page"}),
    ("open youtube", None, {}),
    ("search google for nasi goreng recipe", None, {}),
    ("explain how a CPU works", None, {}),
    ("what time is it?", "get_datetime", {}),
    ("baterai berapa persen?", "get_battery", {}),
    ("turn the volume up", "set_volume", {"direction": "up"}),
    ("play Yellow by Coldplay", "play_music", {}),
    ("putar lagu Hati-Hati di Jalan", "play_music", {}),
    ("shut down the pc", "power", {"action": "shutdown"}),
    ("how do I restart my computer?", None, {}),
    ("good night, I'm tired", None, {}),
    ("hello Jarvis, apa kabar?", None, {}),
    ("what is 12 times 12?", None, {}),
    ("tell me a joke", None, {}),
    ("what is the capital of France?", None, {}),
    ("thanks, that's all", None, {}),
    ("remember that my cat is called Mochi", "remember", {"fact": ANY}),
    ("ingat ya, ulang tahun ibuku tanggal 3 Mei", "remember", {"fact": ANY}),
    ("please remember I'm allergic to peanuts", "remember", {"fact": ANY}),
    ("tolong ingat kalau aku tinggal di Bandung", "remember", {"fact": ANY}),
    ("forget that my cat is called Mochi", "forget", {"fact": ANY}),
    ("lupakan soal ulang tahun ibuku", "forget", {"fact": ANY}),
    ("please forget what I told you about peanuts", "forget", {"fact": ANY}),
    ("hapus dari ingatanmu bahwa aku tinggal di Bandung", "forget", {"fact": ANY}),
    ("how do I remember a password", None, {}),
    ("what is RAM", None, {}),
    ("how do I forget a wifi network", None, {}),
    ("do you remember things?", None, {}),
    ("gimana cara mengingat banyak hal?", None, {}),
    ("kamu bisa lupa nggak?", None, {}),
]


def recorder(name, tool, calls):
    def fn(**arguments):
        calls.append((name, arguments))
        return "ok"

    return replace(tool, fn=fn, dangerous=False)


def mismatch(arguments, key, value):
    if value is ANY:
        return not str(arguments.get(key, "")).strip()
    return arguments.get(key) != value


# The recorder replaces every function, so nothing is stored; the database is a throwaway.
scratch = tempfile.TemporaryDirectory()
all_tools = {
    **TOOLS,
    **memory_tools.build(Facts(Path(scratch.name) / "check_tools.sqlite3")),
}
client = openai.OpenAI(base_url=config.BASE_URL, api_key=config.API_KEY, max_retries=0)
failures = 0
for phrase, expected, wanted in CASES:
    wrong = []
    for _ in range(SAMPLES):
        calls = []
        tools = {name: recorder(name, tool, calls) for name, tool in all_tools.items()}
        Brain(client, config.MODEL, tools=tools, extra_body=config.EXTRA_BODY).ask(
            phrase
        )
        names = [name for name, _ in calls]
        arguments = calls[0][1] if calls else {}
        if (names[:1] or [None]) != [expected] or any(
            mismatch(arguments, key, value) for key, value in wanted.items()
        ):
            wrong.append(json.dumps(calls, ensure_ascii=False))
    failures += len(wrong)
    print(
        f"{SAMPLES - len(wrong)}/{SAMPLES}  {phrase!r}",
        *wrong[:1],
        sep="  " if wrong else "",
    )
scratch.cleanup()
print(f"\nwrong: {failures} of {SAMPLES * len(CASES)}")
sys.exit(1 if failures else 0)
