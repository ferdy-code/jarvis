import ast
import json
import pathlib
import urllib.error
from types import SimpleNamespace

import pytest

from jarvis import web

RSS = b"""<rss><channel><title>Google News</title>
<item><title>Rupiah menguat - detikFinance</title></item>
<item><title>Banjir di Jakarta - Kompas.com</title></item>
</channel></rss>"""

ARTICLE = (
    "<html><body><p>"
    + "Jakarta is the capital of Indonesia. " * 20
    + "</p></body></html>"
)
WIKI = {
    "query": {"pages": {"1": {"index": 1, "title": "Canberra", "extract": "Capital."}}}
}


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

    def fake_get(url, params=None, limit=0):
        calls.append((url, params))
        return body

    monkeypatch.setattr(web, "_get", fake_get)
    monkeypatch.setattr(web, "_client", lambda: client)
    return calls, client


def test_web_module_never_imports_browser():
    source = pathlib.Path(web.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported |= {node.module or ""}
            imported |= {f"{node.module}.{alias.name}" for alias in node.names}
    assert not {name for name in imported if name.endswith("browser")}


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


def test_wiki_lists_the_articles_in_search_rank_order(monkeypatch):
    pages = {"query": {"pages": {
        "9": {"index": 2, "title": "Canberra", "extract": "Canberra is the capital."},
        "3": {"index": 1, "title": "Australia", "extract": "A country."},
    }}}  # fmt: skip
    calls, _ = fake_web(monkeypatch, json.dumps(pages).encode())

    assert web.wiki("capital of Australia", "en") == (
        "Australia: A country.\nCanberra: Canberra is the capital."
    )
    assert calls[0][0] == "https://en.wikipedia.org/w/api.php"


def test_wiki_with_no_article_is_empty(monkeypatch):
    fake_web(monkeypatch, b'{"batchcomplete": ""}')

    assert web.wiki("zzzxqkj", "en") == ""


def test_readable_text_drops_menus_scripts_and_styles():
    html = (
        "<html><head><style>p{}</style><script>var x=1;</script></head><body>"
        "<header>Logo</header><nav><a>Home</a></nav><svg><text>icon</text></svg>"
        "<h1>Title</h1><p>First   line.</p><p>Second<br>line.</p>"
        "<noscript>enable js</noscript><footer>Copyright</footer></body></html>"
    )

    assert web.readable_text(html) == "Title First line. Second line."


@pytest.mark.parametrize(
    ("spoken", "address"),
    [
        ("bbc.com", "https://bbc.com"),
        (" www.kompas.com. ", "https://www.kompas.com"),
        ("http://example.org/news", "http://example.org/news"),
    ],
)
def test_page_address_adds_https_to_a_spoken_domain(spoken, address):
    assert web.page_address(spoken) == address


@pytest.mark.parametrize(
    "spoken",
    ["file:///C:/secret.txt", "javascript:alert(1)", "ftp://example.com", "bbc", ""],
)
def test_page_address_refuses_anything_but_a_web_address(spoken):
    with pytest.raises(ValueError, match="web address|http"):
        web.page_address(spoken)


def test_a_page_is_summarised_from_its_text_with_no_tools(monkeypatch):
    calls, client = fake_web(monkeypatch, ARTICLE.encode())

    answer = web.web_lookup("page", "detik.com", "en")

    request = client.requests[0]
    assert calls[0][0] == "https://detik.com"
    assert answer.endswith("According to Wikipedia, it is Canberra.")
    assert "tools" not in request
    assert "Source: detik.com" in request["messages"][1]["content"]
    assert "<web>\nJakarta is the capital" in request["messages"][1]["content"]


def test_a_long_page_is_cut_to_the_limit(monkeypatch):
    html = "<p>" + "word " * 5000 + "</p>"
    _, client = fake_web(monkeypatch, html.encode())

    web.web_lookup("page", "example.com", "en")

    shown = client.requests[0]["messages"][1]["content"]
    assert len(shown) < web.PAGE_CHARS + 200


def test_a_page_with_thin_text_is_not_summarised(monkeypatch):
    _, client = fake_web(
        monkeypatch, b"<html><body><p>Please log in.</p></body></html>"
    )

    answer = web.web_lookup("page", "example.com", "en")

    assert answer.startswith("error: could not read that page")
    assert "almost no text" in answer
    assert client.requests == []


@pytest.mark.parametrize(
    ("error", "wording"),
    [
        (urllib.error.HTTPError("u", 403, "Forbidden", {}, None), "answered 403"),
        (urllib.error.HTTPError("u", 401, "Unauthorized", {}, None), "answered 401"),
        (TimeoutError("timed out"), "did not answer in time"),
        (urllib.error.URLError("certificate verify failed"), "could not connect"),
    ],
)
def test_a_fetch_failure_is_reported_not_guessed(monkeypatch, error, wording):
    def broken(url, params=None, limit=0):
        raise error

    client = FakeClient()
    monkeypatch.setattr(web, "_get", broken)
    monkeypatch.setattr(web, "_client", lambda: client)

    answer = web.web_lookup("page", "example.com", "en")

    assert answer.startswith("error: could not read that page")
    assert wording in answer
    assert "call no more tools" in answer
    assert client.requests == []


def test_a_bad_address_is_refused_before_any_fetch(monkeypatch):
    calls, _ = fake_web(monkeypatch, ARTICLE.encode())

    answer = web.web_lookup("page", "file:///C:/x", "en")

    assert answer.startswith("error: could not read that page")
    assert calls == []


def test_the_reader_gets_wikipedia_text_as_data_and_no_tools(monkeypatch):
    _, client = fake_web(monkeypatch, json.dumps(WIKI).encode())

    answer = web.web_lookup("wiki", "what is the capital of Australia", "en")

    request = client.requests[0]
    assert answer.endswith("According to Wikipedia, it is Canberra.")
    assert "tools" not in request
    assert "<web>\nCanberra: Capital.\n</web>" in request["messages"][1]["content"]


def test_the_reader_is_told_to_answer_in_the_users_language(monkeypatch):
    _, client = fake_web(monkeypatch, RSS)

    web.web_lookup("news", "", "id")

    assert "Reply in Indonesian." in client.requests[0]["messages"][0]["content"]


def test_nothing_found_is_reported_without_asking_the_model(monkeypatch):
    _, client = fake_web(monkeypatch, b'{"batchcomplete": ""}')

    assert web.web_lookup("wiki", "zzzxqkj", "en").startswith("error:")
    assert client.requests == []


def test_a_network_failure_becomes_an_error_result(monkeypatch):
    def broken(url, params=None, limit=0):
        raise OSError("no internet")

    monkeypatch.setattr(web, "_get", broken)

    assert web.web_lookup("news", "", "en").startswith("error: could not reach the web")


def test_an_unknown_kind_is_refused(monkeypatch):
    fake_web(monkeypatch, RSS)

    assert web.web_lookup("weather", "", "en").startswith("error: kind must be")
