"""Check the real model in multi-turn chats. Needs LlamaStash running.

    uv run python scripts/check_conversation.py [samples-per-scenario]

Run it after changing SYSTEM_PROMPT or the tool descriptions: the wording is
load-bearing and unit tests cannot see it. The clock tool is replaced by one
that moves forward on every call, so a reply is only fresh if the model called
the tool again; copying an earlier answer shows up as a stale minute.

It runs the scenarios twice, without and with three stored facts in the prompt, then
asks about the facts. The memory tools are harmless recorders over a throwaway store.
"""

import sys
import tempfile
from pathlib import Path

from jarvis import config, memory_tools
from jarvis.app import openai
from jarvis.brain import Brain
from jarvis.facts import Facts
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

FACTS = [
    "Kucingku namanya Mochi",
    "My sister's name is Rina",
    "I work night shifts at the hospital",
]

# Each question is (text, language of the question, words one of which must be in the
# reply). The reply must come from the facts alone: no tool may be called.
FACT_QUESTIONS = [
    ("what is my cat called?", "en", ("mochi",)),
    ("kucingku namanya siapa?", "id", ("mochi",)),
    ("what is my sister's name?", "en", ("rina",)),
    ("siapa nama saudara perempuanku?", "id", ("rina",)),
    ("what kind of shifts do I work?", "en", ("night", "malam")),
    ("aku kerja shift apa ya?", "id", ("malam", "night")),
]
# Asked in a fresh chat each: a chat that just answered about Mochi may mention it.
UNRELATED_QUESTIONS = [
    ("what is the capital of Japan?", "en"),
    ("ceritakan lelucon pendek", "id"),
    ("how many days are in a week?", "en"),
]
FACT_WORDS = ("mochi", "rina", "hospital", "rumah sakit")

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
    # The same tool set as the real app; the store is never opened, only named.
    with tempfile.TemporaryDirectory() as folder:
        memory = memory_tools.build(Facts(Path(folder) / "facts.sqlite3"))
    for name, tool in {**TOOLS, **memory}.items():
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


def new_brain(facts):
    return Brain(
        client,
        config.MODEL,
        tools=make_tools(),
        extra_body=config.EXTRA_BODY,
        facts=(lambda: facts) if facts else None,
    )


def run_scenarios(facts):
    global minute
    total = right_data = right_language = 0
    failures = []
    for name, turns in SCENARIOS.items():
        for _ in range(SAMPLES):
            minute = START_MINUTE
            brain = new_brain(facts)
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
    return (
        f"fresh data {right_data}/{total}, reply language {right_language}/{total}",
        failures,
    )


def run_fact_questions():
    right = language = clean = 0
    total_right = total_clean = 0
    failures = []
    for _ in range(SAMPLES):
        brain = new_brain(FACTS)
        for question, lang, words in FACT_QUESTIONS:
            tool_calls.clear()
            reply = brain.ask(question)
            total_right += 1
            ok = any(word in reply.lower() for word in words) and not tool_calls
            right += ok
            language += guess_lang(reply) == lang
            if not ok or guess_lang(reply) != lang:
                failures.append(
                    f"facts: {question!r} tools={tool_calls or '-'} -> {reply!r}"
                )
        for question, lang in UNRELATED_QUESTIONS:
            tool_calls.clear()
            reply = new_brain(FACTS).ask(question)
            total_clean += 1
            ok = not any(word in reply.lower() for word in FACT_WORDS)
            clean += ok
            language += guess_lang(reply) == lang
            if not ok or guess_lang(reply) != lang:
                failures.append(f"unrelated: {question!r} -> {reply!r}")
    total_language = total_right + total_clean
    line = (
        f"facts: right {right}/{total_right}, reply language {language}/{total_language}, "
        f"unrelated clean {clean}/{total_clean}"
    )
    return line, failures


all_failures = []
for label, run in (
    ("", lambda: run_scenarios(None)),
    ("with facts: ", lambda: run_scenarios(FACTS)),
    ("", run_fact_questions),
):
    line, failures = run()
    print(label + line)
    for failure in failures[:8]:
        print("  FAIL", failure)
    all_failures += failures
sys.exit(1 if all_failures else 0)
