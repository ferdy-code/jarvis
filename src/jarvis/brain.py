import json
from collections.abc import Callable

import openai

from jarvis.tools import Tool

OFFLINE_MESSAGE = "My brain is offline. Is LlamaStash running?"
MAX_HISTORY = 20
MAX_TOOL_ROUNDS = 3

# Wording matters: with thinking off, a prompt that only asks for short answers
# made the model skip the tools and invent the time and battery level (0/9 calls).
# Saying it cannot know these things itself fixed that (15/15, 0/9 false calls).
# Spelling times out in Indonesian words was often wrong ("jam enam belas" for
# 18:03), so it must copy them as digits (12/12 correct).
# In a longer chat it copied its own earlier answer instead of calling the tool
# again (a stale time, and English after an Indonesian question), so the last
# two sentences forbid that (fixed 6 of 90 failures, see scripts/check_conversation.py).
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
    "this conversation. Always reply in the language of the user's latest "
    "message, not the language of earlier messages."
)

LANGUAGE_NAMES = {"en": "English", "id": "Indonesian"}


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
        # Only user and assistant text is remembered between turns. Tool calls
        # live in the per-turn message list, so trimming can never split a
        # tool call from its result.
        self.history: list[dict] = []

    def ask(self, text: str, lang: str | None = None) -> str:
        self.history.append({"role": "user", "content": text})
        self.history = self.history[-MAX_HISTORY:]
        messages = [{"role": "system", "content": _system_prompt(lang)}]
        messages += self.history
        try:
            reply = self._converse(messages)
        except openai.APIConnectionError:
            self.history.pop()
            return OFFLINE_MESSAGE
        self.history.append({"role": "assistant", "content": reply})
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
