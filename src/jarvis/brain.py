import json
from collections.abc import Callable

import openai

from jarvis.language import detect_language
from jarvis.tools import Tool

OFFLINE_MESSAGE = "My brain is offline. Is LlamaStash running?"
MAX_TURNS = 10
MAX_TOOL_ROUNDS = 3

# Wording matters: with thinking off, a prompt that only asks for short answers
# made the model skip the tools and invent the time and battery level (0/9 calls).
# Saying it cannot know these things itself fixed that (15/15, 0/9 false calls).
# Spelling times out in Indonesian words was often wrong ("jam enam belas" for
# 18:03), so it must copy them as digits (12/12 correct).
# In a longer chat it copied its own earlier answer instead of calling the tool
# again (a stale time, and English after an Indonesian question), so the last
# two sentences forbid that (fixed 6 of 90 failures, see scripts/check_conversation.py).
# The how-to sentence stops questions being treated as orders: each new tool nudged
# "how do I restart my computer?" into a restart request (3 of 3 after play_music);
# with it, 0 of 27 question phrasings, and all 18 real orders still work. Keep the
# language sentence LAST: with the how-to sentence after it, the reply language was
# wrong 6 of 75 times in the long conversations; this order gives 75 of 75.
# "I'm tired, goodnight" asked for a shutdown 3 times in 3 (with ten tools); the
# greeting sentence brings 42 question/goodbye phrasings to 0 false requests.
SYSTEM_PROMPT = (
    "You are Jarvis, a voice assistant on the user's PC. You cannot know the "
    "current date, time or battery level yourself: always call the matching "
    "tool and never guess. After you have the tool result, answer in 1-3 short "
    "spoken sentences with no markdown, in the language the user writes in "
    "(English or Indonesian). Always write times as digits copied from the "
    "tool result, for example 18:03, never spell them out. Never claim to "
    "have done something unless a tool confirmed it. Things on this PC change "
    "all the time, so for every question about the date, time or battery call "
    "the tool again, even if you already answered such a question earlier in "
    "this conversation. When the user asks how to do something, or what "
    "something is, answer in words; only take an action when the user tells you "
    "to do it. A greeting, goodnight or thank you is not a command: answer it in "
    "words. Always reply in the language of the user's latest message, not the "
    "language of earlier messages."
)

LANGUAGE_NAMES = {"en": "English", "id": "Indonesian"}

# A clock or battery reading is out of date as soon as it is spoken, so a turn that
# used one is not remembered. Kept in the history, the model copied its old answer
# (in its old language) instead of asking the clock again: the stale time and the
# wrong-language reply that no amount of prompt wording fixed for good.
FORGOTTEN_TOOLS = {"get_datetime", "get_battery"}


class Brain:
    def __init__(
        self,
        client,
        model: str,
        tools: dict[str, Tool] | None = None,
        confirm: Callable[[str], bool] | None = None,
        extra_body: dict | None = None,
    ):
        self.client = client
        self.model = model
        self.tools = tools or {}
        # Asked before any dangerous tool runs. With no way to ask, those never run.
        self.confirm = confirm
        self.extra_body = extra_body
        # Each past turn is kept whole: the question, any tool calls and their results,
        # and the reply. With only the reply text remembered, the model never saw itself
        # call a tool and began answering "Musik sudah dipause" without calling one.
        # Whole turns are trimmed together, so a tool call is never cut from its result.
        self.history: list[list[dict]] = []

    def ask(self, text: str, lang: str | None = None) -> str:
        # Told to the model outright when the words make it clear: with only the
        # prompt's instruction, an English tool result ("Saturday, October 10") pulled
        # the reply into English after an Indonesian question (6 of 75 chats).
        lang = lang or detect_language(text)
        messages = [{"role": "system", "content": _system_prompt(lang)}]
        for turn in self.history:
            messages += turn
        start = len(messages)
        messages.append({"role": "user", "content": text})
        try:
            reply = self._converse(messages)
        except openai.APIConnectionError:
            return OFFLINE_MESSAGE
        turn = [*messages[start:], {"role": "assistant", "content": reply}]
        if not _tools_used(turn) & FORGOTTEN_TOOLS:
            self.history = [*self.history, turn][-MAX_TURNS:]
        return reply

    def _converse(self, messages: list[dict]) -> str:
        for _ in range(MAX_TOOL_ROUNDS):
            message = self._complete(messages, with_tools=True)
            if not message.tool_calls:
                return message.content or ""
            messages.append(_assistant_message(message))
            for tool_call in message.tool_calls:
                result = self._run_tool(tool_call)
                messages.append(
                    {"role": "tool", "tool_call_id": tool_call.id, "content": result}
                )
        # Too many tool rounds: make the model answer with what it has.
        return self._complete(messages, with_tools=False).content or ""

    def _complete(self, messages: list[dict], with_tools: bool):
        request = {
            "model": self.model,
            "messages": messages,
            "extra_body": self.extra_body,
        }
        if with_tools and self.tools:
            request["tools"] = [tool.schema for tool in self.tools.values()]
        return self.client.chat.completions.create(**request).choices[0].message

    def _run_tool(self, tool_call) -> str:
        name = tool_call.function.name
        tool = self.tools.get(name)
        if tool is None:
            return f"error: unknown tool {name!r}"
        try:
            arguments = json.loads(tool_call.function.arguments or "{}")
        except json.JSONDecodeError as error:
            return f"error: bad arguments ({error})"
        if tool.dangerous and not self._confirmed(name, arguments):
            return "cancelled by user"
        try:
            return str(tool.fn(**arguments))
        except Exception as error:  # noqa: BLE001 - a broken tool must not crash Jarvis
            return f"error: {error}"

    def _confirmed(self, name: str, arguments: dict) -> bool:
        if self.confirm is None:
            return False
        details = ", ".join(f"{key}={value}" for key, value in arguments.items())
        return self.confirm(f"{name}({details})")


def _tools_used(messages: list[dict]) -> set[str]:
    """The names of the tools called in this turn's messages."""
    return {
        call["function"]["name"]
        for message in messages
        for call in message.get("tool_calls", [])
    }


def _assistant_message(message) -> dict:
    return {
        "role": "assistant",
        "content": message.content or "",
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in message.tool_calls
        ],
    }


def _system_prompt(lang: str | None) -> str:
    if lang in LANGUAGE_NAMES:
        return f"{SYSTEM_PROMPT} The user is speaking {LANGUAGE_NAMES[lang]}."
    return SYSTEM_PROMPT
