import json
from types import SimpleNamespace

from jarvis import web

RSS = b"""<rss><channel><title>Google News</title>
<item><title>Rupiah menguat - detikFinance</title></item>
<item><title>Banjir di Jakarta - Kompas.com</title></item>
</channel></rss>"""


class FakeClient:
    def __init__(self, reply="According to Wikipedia, it is Canberra."):
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.reply = reply

    def create(self, **request):
        self.requests.append(request)
        message = SimpleNamespace(content=self.reply)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def fake_web(monkeypatch, body, client=None):
    calls = []
    client = client or FakeClient()
    monkeypatch.setattr(
        web, "_get", lambda url, params: calls.append((url, params)) or body
    )
    monkeypatch.setattr(web, "_client", lambda: client)
    return calls, client


def test_news_lists_the_headlines_with_their_outlets(monkeypatch):
    calls, _ = fake_web(monkeypatch, RSS)

    headlines = web.news("rupiah", "id")

    assert headlines == "Rupiah menguat - detikFinance\nBanjir di Jakarta - Kompas.com"
    assert calls[0][0].endswith("/rss/search")
    assert calls[0][1]["q"] == "rupiah"
    assert calls[0][1]["hl"] == "id"


def test_news_without_a_topic_asks_for_the_top_stories(monkeypatch):
    calls, _ = fake_web(monkeypatch, RSS)

    web.news("", "en")

    assert calls[0][0].endswith("/rss")
    assert "q" not in calls[0][1]


def test_facts_lists_the_articles_in_search_rank_order(monkeypatch):
    pages = {"query": {"pages": {
        "9": {"index": 2, "title": "Canberra", "extract": "Canberra is the capital."},
        "3": {"index": 1, "title": "Australia", "extract": "A country."},
    }}}  # fmt: skip
    calls, _ = fake_web(monkeypatch, json.dumps(pages).encode())

    assert web.facts("capital of Australia", "en") == (
        "Australia: A country.\nCanberra: Canberra is the capital."
    )
    assert calls[0][0] == "https://en.wikipedia.org/w/api.php"


def test_facts_with_no_article_is_empty(monkeypatch):
    fake_web(monkeypatch, b'{"batchcomplete": ""}')

    assert web.facts("zzzxqkj", "en") == ""


def test_the_reader_gets_the_excerpts_as_data_and_no_tools(monkeypatch):
    pages = {
        "query": {
            "pages": {"1": {"index": 1, "title": "Canberra", "extract": "Capital."}}
        }
    }
    _, client = fake_web(monkeypatch, json.dumps(pages).encode())

    answer = web.web_answer("facts", "what is the capital of Australia", "en")

    request = client.requests[0]
    assert answer.endswith("According to Wikipedia, it is Canberra.")
    assert "tools" not in request
    assert "<web>\nCanberra: Capital.\n</web>" in request["messages"][1]["content"]
    assert "what is the capital of Australia" in request["messages"][1]["content"]


def test_the_reader_is_told_to_answer_in_the_users_language(monkeypatch):
    _, client = fake_web(monkeypatch, RSS)

    web.web_answer("news", "", "id")

    assert "Reply in Indonesian." in client.requests[0]["messages"][0]["content"]


def test_nothing_found_is_reported_without_asking_the_model(monkeypatch):
    _, client = fake_web(monkeypatch, b'{"batchcomplete": ""}')

    assert web.web_answer("facts", "zzzxqkj", "en").startswith("error:")
    assert client.requests == []


def test_a_network_failure_becomes_an_error_result(monkeypatch):
    def broken(url, params):
        raise OSError("no internet")

    monkeypatch.setattr(web, "_get", broken)

    assert web.web_answer("news", "", "en").startswith("error: could not reach the web")


def test_an_unknown_kind_is_refused(monkeypatch):
    fake_web(monkeypatch, RSS)

    assert web.web_answer("weather", "", "en").startswith("error: kind must be")
