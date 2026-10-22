import pytest

import webcite
from citations import CitationError, format_entry
from webcite import check_url, extract

NEWS_PAGE = """
<html><head>
<title>Bees in decline | The Daily Planet</title>
<meta property="og:site_name" content="The Daily Planet">
<meta property="og:title" content="Bees in decline | The Daily Planet">
<meta name="author" content="By Jane Smith and Ali Khan">
<meta property="article:published_time" content="2023-05-14T09:00:00Z">
</head><body>...</body></html>
"""

JSON_LD_PAGE = """
<html><head><title>Fallback title</title>
<script type="application/ld+json">
{"@context": "https://schema.org", "@graph": [
  {"@type": "WebSite", "name": "Science Hub"},
  {"@type": "Article", "headline": "How leaves turn red", "datePublished": "2021-10-02",
   "author": [{"@type": "Person", "name": "Maria Lopez"}], "publisher": {"name": "Science Hub"}}
]}
</script></head></html>
"""

ACADEMIC_PAGE = """
<meta name="citation_title" content="Deep learning">
<meta name="citation_author" content="LeCun, Yann">
<meta name="citation_author" content="Bengio, Yoshua">
<meta name="citation_publication_date" content="2015/05/28">
<meta name="citation_journal_title" content="Nature">
"""


def test_open_graph_and_author_meta():
    info = extract(NEWS_PAGE, "https://dailyplanet.example/bees")
    assert info["title"] == "Bees in decline"
    assert info["authors"] == ["Jane Smith", "Ali Khan"]
    assert info["year"] == "2023" and info["site"] == "The Daily Planet"


def test_json_ld():
    info = extract(JSON_LD_PAGE, "https://sciencehub.example/leaves")
    assert info["title"] == "How leaves turn red"
    assert info["authors"] == ["Maria Lopez"]
    assert info["year"] == "2021" and info["site"] == "Science Hub"


def test_academic_citation_tags_win():
    info = extract(ACADEMIC_PAGE, "https://www.nature.com/articles/nature14539")
    assert info["authors"] == ["LeCun, Yann", "Bengio, Yoshua"]
    assert info["year"] == "2015" and info["site"] == "Nature"


def test_bare_page_falls_back_to_title_and_hostname():
    info = extract("<title>  Just a   page </title>", "https://www.example.org/x")
    assert info["title"] == "Just a page" and info["authors"] == [] and info["site"] == "example.org"


def test_wikipedia_style_page():
    page = """<title>Photosynthesis - Wikipedia</title>
    <script type="application/ld+json">{"@type": "Article", "name": "Photosynthesis", "datePublished": "2001-11-05",
      "author": {"@type": "Organization", "name": "Contributors to Wikimedia projects"},
      "publisher": {"@type": "Organization", "name": "Wikimedia Foundation, Inc."}}</script>"""
    info = extract(page, "https://en.wikipedia.org/wiki/Photosynthesis")
    assert info["title"] == "Photosynthesis" and info["site"] == "Wikipedia" and info["authors"] == []


def test_title_suffix_names_the_site():
    info = extract("<title>Climate - BBC News</title>", "https://www.bbc.com/news/climate")
    assert info["title"] == "Climate" and info["site"] == "BBC News"


def test_title_dash_kept_when_not_the_site():
    info = extract("<title>Cats - a short history</title>", "https://pets.example/cats")
    assert info["title"] == "Cats - a short history"


def test_author_urls_are_ignored():
    page = '<meta property="article:author" content="https://facebook.com/someone"><title>T</title>'
    assert extract(page, "https://a.example/")["authors"] == []


@pytest.mark.parametrize("url", ["http://localhost:8501", "http://127.0.0.1/", "http://10.0.0.5/", "http://192.168.1.1/admin"])
def test_private_addresses_blocked(url):
    with pytest.raises(CitationError, match="private or local"):
        check_url(url)


class FakeSock:
    def __init__(self, ip):
        self.ip = ip

    def getpeername(self):
        return (self.ip, 443)


class FakeRaw:
    def __init__(self, ip):
        self.connection = type("C", (), {"sock": FakeSock(ip)})() if ip else None


def test_connected_ip_must_be_public():
    resp = type("R", (), {})()
    for ip, ok in (("93.184.216.34", True), ("127.0.0.1", False), ("10.1.2.3", False), (None, False)):
        resp.raw = FakeRaw(ip)
        assert webcite.connected_to_public_ip(resp) is ok, ip


def test_dns_rebinding_blocked(monkeypatch):
    """DNS said public, but the connection actually went to a private address."""
    monkeypatch.setattr(webcite.socket, "getaddrinfo", lambda host, port: [(None, None, None, "", ("93.184.216.34", port))])

    class Resp:
        raw = FakeRaw("169.254.169.254")
        is_redirect = False
        closed = False

        def close(self):
            Resp.closed = True

    monkeypatch.setattr(webcite.requests, "get", lambda *a, **k: Resp())
    with pytest.raises(CitationError, match="private or local"):
        webcite.fetch_html("https://rebind.example/")
    assert Resp.closed


def test_non_web_scheme_rejected():
    with pytest.raises(CitationError):
        check_url("file:///C:/Windows/win.ini")


@pytest.fixture(autouse=False)
def public_dns(monkeypatch):
    """lookup_url re-checks the address; answer DNS with a public IP so tests stay offline."""
    monkeypatch.setattr(webcite.socket, "getaddrinfo", lambda host, port: [(None, None, None, "", ("93.184.216.34", port))])


def test_lookup_url_builds_web_reference(monkeypatch, public_dns):
    monkeypatch.setattr(webcite, "fetch_html", lambda url: (url, NEWS_PAGE))
    ref = webcite.lookup_url("https://dailyplanet.example/bees", set())
    assert ref.kind == "web" and ref.key == "smith2023"
    assert format_entry(ref, "APA").startswith("Smith, J., & Khan, A. (2023). *Bees in decline*. The Daily Planet.")


def test_redirect_junk_query_dropped(monkeypatch, public_dns):
    monkeypatch.setattr(webcite, "fetch_html", lambda url: (url + "?error=cookies_not_supported", ACADEMIC_PAGE))
    ref = webcite.lookup_url("https://www.nature.com/articles/nature14539", set())
    assert ref.url == "https://www.nature.com/articles/nature14539"


def test_no_author_key_uses_site_name(monkeypatch, public_dns):
    monkeypatch.setattr(webcite, "fetch_html", lambda url: (url, "<title>Photosynthesis - Wikipedia</title>"
                                                              '<meta property="og:site_name" content="Wikipedia">'))
    ref = webcite.lookup_url("https://en.wikipedia.org/wiki/Photosynthesis", set())
    assert ref.title == "Photosynthesis" and ref.key == "wikipedia"
