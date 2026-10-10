"""Check the real model in multi-turn chats. Needs LlamaStash running.

    uv run python scripts/check_conversation.py [samples-per-scenario]

Run it after changing SYSTEM_PROMPT or the tool descriptions: the wording is
load-bearing and unit tests cannot see it. The clock tool is replaced by one
that moves forward on every call, so a reply is only fresh if the model called
the tool again; copying an earlier answer shows up as a stale minute.
"""

import sys

from jarvis import config
from jarvis.app import openai
from jarvis.brain import Brain
from jarvis.tools import TOOLS, Tool
from jarvis.tts import guess_lang

SAMPLES = int(sys.argv[1]) if len(sys.argv) > 1 else 3
START_MINUTE = 30

# Each turn is (question, language of the question, check):
#   "time": the reply must show the clock's latest minute
#   "tool": the clock tool must have been called this turn
#   None:   no tool check (the reply language is always checked)
SCENARIOS = {
    "en->id time": [
        ("what time is it?", "en", "time"),
        ("jam berapa sekarang?", "id", "time"),
    ],
    "id->en time": [
        ("jam berapa sekarang?", "id", "time"),
        ("what time is it?", "en", "time"),
    ],
    "en->en time": [
        ("what time is it?", "en", "time"),
        ("and what time is it now?", "en", "time"),
    ],
    "id->id time": [
        ("jam berapa sekarang?", "id", "time"),
        ("sekarang jam berapa ya?", "id", "time"),
    ],
    "time, chat, time": [
        ("what time is it?", "en", "time"),
        ("halo, apa kabar?", "id", None),
        ("jam berapa sekarang?", "id", "time"),
    ],
    "time, day": [
        ("what time is it?", "en", "time"),
        ("what day is it?", "en", "tool"),
    ],
    "time, date in id": [
        ("what time is it?", "en", "time"),
        ("tanggal berapa hari ini?", "id", "tool"),
    ],
    "id date, en time": [
        ("hari apa hari ini?", "id", "tool"),
        ("what time is it?", "en", "time"),
    ],
    "chat x4 then time": [
        ("halo", "id", None),
        ("how are you?", "en", None),
        ("apa kabar?", "id", None),
        ("tell me a short joke", "en", None),
        ("what time is it?", "en", "time"),
    ],
    "time x3 mixed": [
        ("what time is it?", "en", "time"),
        ("jam berapa sekarang?", "id", "time"),
        ("what time is it now?", "en", "time"),
    ],
}

client = openai.OpenAI(base_url=config.BASE_URL, api_key=config.API_KEY, max_retries=0)
minute = START_MINUTE
tool_calls: list[str] = []


def clock() -> str:
    global minute
    minute += 1
    tool_calls.append("get_datetime")
    return f"Saturday 10 October 2026, 18:{minute}"


def harmless(name):
    def run(**_):
        tool_calls.append(name)
        return "ok"

    return run


def make_tools():
    tools = {}
    for name, tool in TOOLS.items():
        fn = clock if name == "get_datetime" else harmless(name)
        tools[name] = Tool(fn=fn, schema=tool.schema, dangerous=tool.dangerous)
    return tools


def passed(check, reply) -> bool:
    if check == "tool":
        return "get_datetime" in tool_calls
    if check == "time":
        # the clock must really have been read: a copied answer can look fresh
        return "get_datetime" in tool_calls and f"18:{minute}" in reply
    return True


total = right_data = right_language = 0
failures = []
for name, turns in SCENARIOS.items():
    for _ in range(SAMPLES):
        minute = START_MINUTE
        brain = Brain(
            client, config.MODEL, tools=make_tools(), extra_body=config.EXTRA_BODY
        )
        for question, language, check in turns:
            tool_calls.clear()
            reply = brain.ask(question)
            total += 1
            ok_data = passed(check, reply)
            ok_language = guess_lang(reply) == language
            right_data += ok_data
            right_language += ok_language
            if not (ok_data and ok_language):
                failures.append(
                    f"{name}: {question!r} tools={tool_calls or '-'} -> {reply!r}"
                )

print(f"fresh data {right_data}/{total}, reply language {right_language}/{total}")
for failure in failures[:8]:
    print("  FAIL", failure)
sys.exit(1 if failures else 0)
