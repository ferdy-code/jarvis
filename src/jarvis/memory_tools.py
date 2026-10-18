from jarvis.facts import Facts
from jarvis.tools import Tool, _tool

# Both refuse after web_lookup: page text must not be able to write into memory.
_AFTER_WEB = frozenset({"web_lookup"})


def build(facts: Facts) -> dict[str, Tool]:
    """The remember and forget tools, bound to one facts store."""

    def remember(fact: str) -> str:
        if facts.add(fact) == "duplicate":
            return "already remembered"
        return f"remembered: {' '.join(fact.split())}"

    def forget(fact: str) -> str:
        removed = facts.remove(fact)
        return "\n".join(f"forgot: {text}" for text in removed) or "nothing matched"

    # Shortening both descriptions to one sentence each made "news today" call
    # get_datetime first (6 of 126); the longer wording below kept every case right.
    return {
        "remember": _tool(
            remember,
            "Save one short fact about the user or their things for later, only when "
            "the user explicitly asks you to remember it. Never for passwords, keys or "
            "numbers. Questions about remembering in general call no tool.",
            properties={
                "fact": {
                    "type": "string",
                    "description": "The fact as one short sentence",
                }
            },
            required=["fact"],
            refused_after=_AFTER_WEB,
        ),
        "forget": _tool(
            forget,
            "Remove something you were asked to remember, only when the user "
            "explicitly asks you to forget it. Questions about forgetting in general "
            "call no tool.",
            properties={
                "fact": {
                    "type": "string",
                    "description": "A few words from the fact to remove",
                }
            },
            required=["fact"],
            refused_after=_AFTER_WEB,
        ),
    }
