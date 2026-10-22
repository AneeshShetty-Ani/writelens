from urllib.parse import parse_qs, urlparse

from feedback import issue_url
from highlight import find_spans, render_html


def test_issue_url():
    url = issue_url("Bug report (something isn't working)", "Crash", "Steps here", "@me", "tester", repo="o/r")
    parsed = urlparse(url)
    assert parsed.netloc == "github.com" and parsed.path == "/o/r/issues/new"
    q = parse_qs(parsed.query)
    assert q["title"] == ["[Bug report] Crash"]
    assert q["labels"] == ["bug"]
    assert "Steps here" in q["body"][0] and "@me" in q["body"][0] and "tester" in q["body"][0]


def test_issue_url_truncates_long_description():
    url = issue_url("Question or other feedback", "T", "x" * 10_000)
    assert len(url) < 6000


def test_find_spans_categories():
    text = "Due to the fact that it rained, the match was cancelled by the referee. We really left."
    cats = {c for _, _, c in find_spans(text)}
    assert {"wordy", "passive", "adverb"} <= cats


def test_wordy_spans_do_not_double_count():
    text = "Due to the fact that it rained."
    wordy = [(s, e) for s, e, c in find_spans(text) if c == "wordy"]
    assert wordy == [(0, len("Due to the fact that"))]


def test_long_sentence_span():
    long = " ".join(["word"] * 35) + "."
    spans = find_spans("Short. " + long)
    assert (7, 7 + len(long), "long") in spans


def test_render_html_nests_overlaps_and_escapes():
    out = render_html("a <b> c", [(0, 5, "passive"), (2, 5, "adverb")])
    assert '<span class="uf-passive" title="Passive voice">a </span>' in out
    assert 'class="uf-adverb uf-passive"' in out and "&lt;b&gt;" in out
    assert out.endswith(" c</div>")
