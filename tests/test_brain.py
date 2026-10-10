from types import SimpleNamespace

import httpx2  # the HTTP layer openai 3.x is built on
import openai

from jarvis.brain import OFFLINE_MESSAGE, Brain
from jarvis.tools import Tool


def call(name, arguments="{}", id="call-1"):
    """A scripted model reply that asks for one tool call."""
    function = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(
        content=None, tool_calls=[SimpleNamespace(id=id, function=function)]
    )


def tool(fn):
    return Tool(fn=fn, schema={"type": "function", "function": {"name": "t"}})


class FakeClient:
    """Stands in for openai.OpenAI: returns scripted replies, records requests.

    A reply is either plain text or a message built with call().
    """

    def __init__(self, replies=None, error=None):
        self.replies = list(replies or [])
        self.error = error
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        reply = self.replies.pop(0)
        if isinstance(reply, str):
            reply = SimpleNamespace(content=reply, tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=reply)])


def connection_error():
    return openai.APIConnectionError(request=httpx2.Request("POST", "http://x/v1"))


def test_ask_returns_the_model_reply():
    brain = Brain(FakeClient(["Hello there."]), model="m")

    assert brain.ask("hi") == "Hello there."


def test_ask_sends_system_prompt_then_user_message():
    client = FakeClient(["ok"])

    Brain(client, model="m").ask("halo")

    messages = client.requests[0]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": "halo"}


def test_ask_remembers_earlier_turns():
    client = FakeClient(["first", "second"])
    brain = Brain(client, model="m")

    brain.ask("one")
    brain.ask("two")

    sent = [m["content"] for m in client.requests[1]["messages"][1:]]
    assert sent == ["one", "first", "two"]


def test_history_is_trimmed_to_the_last_20_messages():
    client = FakeClient([f"reply {i}" for i in range(15)])
    brain = Brain(client, model="m")

    for i in range(15):
        brain.ask(f"question {i}")

    sent = client.requests[-1]["messages"]
    assert len(sent) == 1 + 20
    assert sent[-1]["content"] == "question 14"


def test_language_hint_is_added_to_the_system_prompt_only_when_given():
    client = FakeClient(["a", "b"])
    brain = Brain(client, model="m")

    brain.ask("x", lang="id")
    brain.ask("y")

    assert (
        "The user is speaking Indonesian"
        in client.requests[0]["messages"][0]["content"]
    )
    assert "The user is speaking" not in client.requests[1]["messages"][0]["content"]


def test_extra_body_is_passed_to_the_client():
    client = FakeClient(["ok"])

    Brain(client, model="m", extra_body={"k": "v"}).ask("hi")

    assert client.requests[0]["extra_body"] == {"k": "v"}


def test_offline_server_returns_the_offline_message():
    brain = Brain(FakeClient(error=connection_error()), model="m")

    assert brain.ask("hi") == OFFLINE_MESSAGE


def test_failed_turn_is_not_kept_in_history():
    client = FakeClient(["ok"])
    brain = Brain(client, model="m")
    client.error = connection_error()
    brain.ask("lost")
    client.error = None

    brain.ask("hello")

    sent = [m["content"] for m in client.requests[-1]["messages"][1:]]
    assert sent == ["hello"]


def tool_results(client, request_index):
    """The tool-role messages the model was shown in one request."""
    return [
        m for m in client.requests[request_index]["messages"] if m["role"] == "tool"
    ]


def test_tool_schemas_are_sent_only_when_there_are_tools():
    with_tools = FakeClient(["ok"])
    without_tools = FakeClient(["ok"])

    Brain(with_tools, model="m", tools={"t": tool(lambda: "x")}).ask("hi")
    Brain(without_tools, model="m").ask("hi")

    assert with_tools.requests[0]["tools"] == [
        {"type": "function", "function": {"name": "t"}}
    ]
    assert "tools" not in without_tools.requests[0]


def test_tool_call_runs_the_tool_and_returns_the_final_reply():
    client = FakeClient([call("clock"), "It is 10:00."])
    brain = Brain(client, model="m", tools={"clock": tool(lambda: "10:00")})

    reply = brain.ask("what time is it?")

    assert reply == "It is 10:00."
    assert tool_results(client, 1) == [
        {"role": "tool", "tool_call_id": "call-1", "content": "10:00"}
    ]


def test_tool_arguments_are_passed_to_the_tool():
    client = FakeClient([call("add", '{"a": 2, "b": 3}'), "5"])
    brain = Brain(client, model="m", tools={"add": tool(lambda a, b: str(a + b))})

    brain.ask("2+3?")

    assert tool_results(client, 1)[0]["content"] == "5"


def test_tool_that_raises_becomes_an_error_result():
    def broken():
        raise RuntimeError("disk on fire")

    client = FakeClient([call("broken"), "Sorry, that failed."])
    brain = Brain(client, model="m", tools={"broken": tool(broken)})

    reply = brain.ask("do it")

    assert reply == "Sorry, that failed."
    assert tool_results(client, 1)[0]["content"] == "error: disk on fire"


def test_unknown_tool_becomes_an_error_result():
    client = FakeClient([call("nope"), "I can't do that."])
    brain = Brain(client, model="m", tools={"clock": tool(lambda: "10:00")})

    brain.ask("do it")

    assert tool_results(client, 1)[0]["content"] == "error: unknown tool 'nope'"


def test_malformed_tool_arguments_become_an_error_result():
    client = FakeClient([call("clock", "{not json"), "Sorry."])
    brain = Brain(client, model="m", tools={"clock": tool(lambda: "10:00")})

    brain.ask("what time is it?")

    assert tool_results(client, 1)[0]["content"].startswith("error: bad arguments")


def test_tool_calls_stop_after_three_rounds():
    runs = []
    client = FakeClient([call("loop")] * 3 + ["Giving up."])
    brain = Brain(
        client, model="m", tools={"loop": tool(lambda: runs.append(1) or "again")}
    )

    reply = brain.ask("go")

    assert reply == "Giving up."
    assert len(runs) == 3
    assert "tools" not in client.requests[-1]


def test_history_keeps_only_the_text_of_a_tool_turn():
    client = FakeClient([call("clock"), "It is 10:00.", "ok"])
    brain = Brain(client, model="m", tools={"clock": tool(lambda: "10:00")})

    brain.ask("time?")
    brain.ask("thanks")

    sent = client.requests[-1]["messages"][1:]
    assert [(m["role"], m["content"]) for m in sent] == [
        ("user", "time?"),
        ("assistant", "It is 10:00."),
        ("user", "thanks"),
    ]
