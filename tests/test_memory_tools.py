import json

from test_brain import FakeClient, call

from jarvis import memory_tools
from jarvis.brain import Brain
from jarvis.facts import Facts


def setup(tmp_path):
    facts = Facts(tmp_path / "f.sqlite3")
    return facts, memory_tools.build(facts)


def result_of(tools, name, fact):
    """What Brain would show the model for one call, errors included."""
    client = FakeClient([call(name, json.dumps({"fact": fact})), "done"])
    Brain(client, model="m", tools=tools).ask("x")
    return client.requests[1]["messages"][-1]["content"]


def test_the_tools_are_safe_and_refuse_after_web_content(tmp_path):
    _facts, tools = setup(tmp_path)

    assert set(tools) == {"remember", "forget"}
    for tool in tools.values():
        assert not tool.dangerous
        assert tool.refused_after == {"web_lookup"}
        assert tool.schema["function"]["parameters"]["required"] == ["fact"]


def test_remember_stores_the_fact(tmp_path):
    facts, tools = setup(tmp_path)

    assert result_of(tools, "remember", "my cat is called Mochi") == (
        "remembered: my cat is called Mochi"
    )
    assert facts.all() == ["my cat is called Mochi"]


def test_remember_the_same_fact_again_says_so(tmp_path):
    facts, tools = setup(tmp_path)
    result_of(tools, "remember", "my cat is called Mochi")

    assert result_of(tools, "remember", "My Cat is called mochi") == (
        "already remembered"
    )
    assert len(facts.all()) == 1


def test_remember_refuses_a_password_as_brain_shows_it(tmp_path):
    facts, tools = setup(tmp_path)

    assert result_of(tools, "remember", "my password is hunter2") == (
        "error: I do not store passwords, keys or card or ID numbers"
    )
    assert facts.all() == []


def test_remember_a_too_short_fact_is_an_error(tmp_path):
    _facts, tools = setup(tmp_path)

    assert result_of(tools, "remember", "hi").startswith("error: a fact must be")


def test_remember_when_full_tells_the_model_to_ask_what_to_forget(tmp_path):
    facts, tools = setup(tmp_path)
    for n in range(30):
        facts.add(f"fact number {n}")

    assert result_of(tools, "remember", "one more") == (
        "error: memory is full (30 facts); ask the user which one to forget"
    )


def test_forget_removes_the_matching_fact(tmp_path):
    facts, tools = setup(tmp_path)
    facts.add("my cat is called Mochi")

    assert result_of(tools, "forget", "cat") == "forgot: my cat is called Mochi"
    assert facts.all() == []


def test_forget_reports_one_line_per_removed_fact(tmp_path):
    facts, tools = setup(tmp_path)
    facts.add("my cat is called Mochi")
    facts.add("Mochi eats fish")
    facts.add("my dog is Rex")

    assert result_of(tools, "forget", "mochi") == (
        "forgot: my cat is called Mochi\nforgot: Mochi eats fish"
    )
    assert facts.all() == ["my dog is Rex"]


def test_forget_with_no_match_says_so(tmp_path):
    facts, tools = setup(tmp_path)
    facts.add("my cat is called Mochi")

    assert result_of(tools, "forget", "parrot") == "nothing matched"
    assert len(facts.all()) == 1


def test_forget_with_a_tiny_query_is_an_error_and_removes_nothing(tmp_path):
    facts, tools = setup(tmp_path)
    facts.add("my cat is called Mochi")

    assert result_of(tools, "forget", "a").startswith("error: say at least 3")
    assert len(facts.all()) == 1
