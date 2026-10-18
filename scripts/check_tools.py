"""Check that the real model picks the right tool for typical requests. Needs LlamaStash.

    uv run python scripts/check_tools.py [samples-per-phrase]

Run it after adding a tool or changing a tool description or the system prompt: every
new tool has shifted how the model treats older requests. Every tool is replaced by
a recorder that returns a canned result, so nothing really happens on the PC.
"""

import json
import sys
from dataclasses import replace

from jarvis import config
from jarvis.app import openai
from jarvis.brain import Brain
from jarvis.tools import TOOLS

SAMPLES = int(sys.argv[1]) if len(sys.argv) > 1 else 3

# (phrase, expected tool or None for "no tool", expected arguments that must match)
CASES = [
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
]


def recorder(name, tool, calls):
    def fn(**arguments):
        calls.append((name, arguments))
        return "ok"

    return replace(tool, fn=fn, dangerous=False)


client = openai.OpenAI(base_url=config.BASE_URL, api_key=config.API_KEY, max_retries=0)
failures = 0
for phrase, expected, wanted in CASES:
    wrong = []
    for _ in range(SAMPLES):
        calls = []
        tools = {name: recorder(name, tool, calls) for name, tool in TOOLS.items()}
        Brain(client, config.MODEL, tools=tools, extra_body=config.EXTRA_BODY).ask(
            phrase
        )
        names = [name for name, _ in calls]
        arguments = calls[0][1] if calls else {}
        if (names[:1] or [None]) != [expected] or any(
            arguments.get(key) != value for key, value in wanted.items()
        ):
            wrong.append(json.dumps(calls, ensure_ascii=False))
    failures += len(wrong)
    print(
        f"{SAMPLES - len(wrong)}/{SAMPLES}  {phrase!r}",
        *wrong[:1],
        sep="  " if wrong else "",
    )
print(f"\nwrong: {failures} of {SAMPLES * len(CASES)}")
sys.exit(1 if failures else 0)
