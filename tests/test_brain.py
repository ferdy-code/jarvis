from types import SimpleNamespace

import httpx2  # the HTTP layer openai 3.x is built on
import openai

from jarvis.brain import OFFLINE_MESSAGE, Brain


class FakeClient:
    """Stands in for openai.OpenAI: returns scripted replies, records requests."""

    def __init__(self, replies=None, error=None):
        self.replies = list(replies or [])
        self.error = error
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        message = SimpleNamespace(content=self.replies.pop(0))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


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
