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


def tool(fn, dangerous=False):
    schema = {"type": "function", "function": {"name": "t"}}
    return Tool(fn=fn, schema=schema, dangerous=dangerous)


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


def test_history_is_trimmed_to_the_last_10_turns():
    client = FakeClient([f"reply {i}" for i in range(15)])
    brain = Brain(client, model="m")

    for i in range(15):
        brain.ask(f"question {i}")

    sent = client.requests[-1]["messages"]
    assert len(sent) == 1 + 10 * 2 + 1  # system, 10 earlier turns, the new question
    assert sent[1]["content"] == "question 4"
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


def test_a_past_tool_turn_is_remembered_with_its_tool_call_and_result():
    # With only the reply text remembered, the model started answering "Musik sudah
    # dipause" without calling the tool at all: it copied its own earlier claims.
    client = FakeClient([call("volume"), "Volume 90%.", "Okay."])
    brain = Brain(client, model="m", tools={"volume": tool(lambda: "volume 90%")})

    brain.ask("turn it down")
    brain.ask("thanks")

    sent = client.requests[-1]["messages"][1:]
    assert [m["role"] for m in sent] == [
        "user",
        "assistant",
        "tool",
        "assistant",
        "user",
    ]
    assert sent[1]["tool_calls"][0]["function"]["name"] == "volume"
    assert sent[2] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": "volume 90%",
    }


def risky_brain(client, confirm, runs):
    risky = tool(lambda action: runs.append(action) or "done", dangerous=True)
    return Brain(client, model="m", tools={"power": risky}, confirm=confirm)


def test_dangerous_tool_runs_after_the_user_confirms():
    runs, questions = [], []
    client = FakeClient([call("power", '{"action": "restart"}'), "Restarting."])
    brain = risky_brain(client, lambda q: questions.append(q) or True, runs)

    reply = brain.ask("restart the pc")

    assert runs == ["restart"]
    assert reply == "Restarting."
    assert "power" in questions[0] and "restart" in questions[0]


def test_dangerous_tool_does_not_run_when_the_user_refuses():
    runs = []
    client = FakeClient([call("power", '{"action": "shutdown"}'), "Okay, cancelled."])
    brain = risky_brain(client, lambda q: False, runs)

    reply = brain.ask("shut down")

    assert runs == []
    assert reply == "Okay, cancelled."
    assert tool_results(client, 1)[0]["content"] == "cancelled by user"


def test_dangerous_tool_does_not_run_when_nobody_can_be_asked():
    runs = []
    client = FakeClient([call("power", '{"action": "shutdown"}'), "I can't."])
    brain = risky_brain(client, confirm=None, runs=runs)

    brain.ask("shut down")

    assert runs == []
    assert tool_results(client, 1)[0]["content"].startswith("cancelled")


def test_safe_tool_never_asks_for_confirmation():
    asked = []
    client = FakeClient([call("clock"), "10:00."])
    brain = Brain(
        client,
        model="m",
        tools={"clock": tool(lambda: "10:00")},
        confirm=lambda q: asked.append(q) or True,
    )

    brain.ask("time?")

    assert asked == []


def system_prompt(client, request_index=0):
    return client.requests[request_index]["messages"][0]["content"]


def test_the_language_of_a_clearly_indonesian_message_is_told_to_the_model():
    client = FakeClient(["ok"])

    Brain(client, model="m").ask("jam berapa sekarang?")

    assert "The user is speaking Indonesian" in system_prompt(client)


def test_the_language_of_a_clearly_english_message_is_told_to_the_model():
    client = FakeClient(["ok"])

    Brain(client, model="m").ask("what time is it?")

    assert "The user is speaking English" in system_prompt(client)


def test_a_message_that_does_not_show_its_language_gets_no_hint():
    client = FakeClient(["ok"])

    Brain(client, model="m").ask("kecilkan volume")

    assert "The user is speaking" not in system_prompt(client)


def test_the_hint_follows_the_latest_message_not_the_earlier_ones():
    client = FakeClient(["one", "two"])
    brain = Brain(client, model="m")

    brain.ask("what time is it?")
    brain.ask("jam berapa sekarang?")

    assert "speaking English" in system_prompt(client, 0)
    assert "speaking Indonesian" in system_prompt(client, 1)


def test_a_language_given_by_the_caller_wins():
    client = FakeClient(["ok"])

    Brain(client, model="m").ask("jam berapa sekarang?", lang="en")

    assert "speaking English" in system_prompt(client)


def sent_texts(client, request_index):
    """What the model was shown (apart from the system prompt) in one request."""
    return [
        m["content"]
        for m in client.requests[request_index]["messages"][1:]
        if m["role"] in ("user", "assistant") and m.get("content")
    ]


def named_tool(name, fn):
    return Tool(fn=fn, schema={"type": "function", "function": {"name": name}})


def test_a_clock_reading_is_not_kept_in_the_conversation():
    # a copied "It is 18:31" (in English, after an Indonesian question) was the bug
    client = FakeClient([call("get_datetime"), "It is 18:31.", "Okay."])
    brain = Brain(
        client,
        model="m",
        tools={"get_datetime": named_tool("get_datetime", lambda: "18:31")},
    )

    brain.ask("what time is it?")
    brain.ask("thanks")

    assert sent_texts(client, 2) == ["thanks"]


def test_a_battery_reading_is_not_kept_either():
    client = FakeClient([call("get_battery"), "85%.", "Okay."])
    brain = Brain(
        client,
        model="m",
        tools={"get_battery": named_tool("get_battery", lambda: "85%")},
    )

    brain.ask("battery?")
    brain.ask("thanks")

    assert sent_texts(client, 2) == ["thanks"]


def test_other_tool_turns_are_still_remembered_so_that_again_works():
    client = FakeClient([call("set_volume"), "Volume 90%.", "Volume 80%."])
    brain = Brain(
        client,
        model="m",
        tools={"set_volume": named_tool("set_volume", lambda: "volume 90%")},
    )

    brain.ask("turn it down")
    brain.ask("and again")

    assert sent_texts(client, 2) == ["turn it down", "Volume 90%.", "and again"]


def test_forgetting_a_clock_reading_keeps_the_rest_of_the_chat():
    client = FakeClient(["Hello!", call("get_datetime"), "It is 18:31.", "Fine."])
    brain = Brain(
        client,
        model="m",
        tools={"get_datetime": named_tool("get_datetime", lambda: "18:31")},
    )

    brain.ask("hi")
    brain.ask("what time is it?")
    brain.ask("how are you?")

    assert sent_texts(client, 3) == ["hi", "Hello!", "how are you?"]


def test_the_reply_to_the_clock_question_itself_is_still_returned():
    client = FakeClient([call("get_datetime"), "It is 18:31."])
    brain = Brain(
        client,
        model="m",
        tools={"get_datetime": named_tool("get_datetime", lambda: "18:31")},
    )

    assert brain.ask("what time is it?") == "It is 18:31."


def test_trimming_the_history_never_separates_a_tool_call_from_its_result():
    replies = []
    for _ in range(14):
        replies += [call("volume"), "Done."]
    client = FakeClient(replies)
    brain = Brain(client, model="m", tools={"volume": tool(lambda: "ok")})

    for i in range(14):
        brain.ask(f"turn {i}")

    sent = client.requests[-1]["messages"][1:]
    assert sent[0]["role"] == "user"  # the oldest kept message starts a turn
    for position, message in enumerate(sent):
        if message["role"] == "tool":
            assert sent[position - 1]["role"] == "assistant"
            assert sent[position - 1]["tool_calls"][0]["id"] == message["tool_call_id"]
