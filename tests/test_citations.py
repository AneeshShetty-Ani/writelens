import json

import pytest
import requests

import citations
from citations import (
    CitationError, Reference, format_entry, from_crossref, from_csl_json, insert_citations, make_key,
    normalize_doi, reference_list, to_bibtex, to_csl_json,
)

ONE = Reference(key="smith2020", kind="article", title="Sleep and memory", authors=["Smith, Jane"], year="2020",
                container="Nature", volume="5", issue="2", pages="10-20", doi="10.1000/xyz")
TWO = Reference(key="lee2019", kind="book", title="Writing Well", authors=["Lee, Anna", "Park, Min"], year="2019", container="Penguin")
MANY = Reference(key="ng2021", kind="web", title="A web page", authors=["Ng, A", "Bo, C", "Wu, D"], year="2021",
                 container="Example", url="https://example.com")
REFS = [ONE, TWO, MANY]


def test_normalize_isbn():
    assert citations.normalize_isbn("ISBN 978-0-14-143951-8") == "9780141439518"
    assert citations.normalize_isbn("isbn-10: 0-306-40615-2") == "0306406152"
    assert citations.normalize_isbn("080442957X") == "080442957X"
    with pytest.raises(CitationError, match="last digit"):
        citations.normalize_isbn("978-0-14-143951-9")
    with pytest.raises(CitationError, match="doesn't look like an ISBN"):
        citations.normalize_isbn("12345")


class FakeLibrary:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_lookup_isbn(monkeypatch):
    book = {"title": "Pride and Prejudice", "subtitle": "A Novel", "authors": [{"name": "Jane Austen"}],
            "publishers": [{"name": "Penguin Books"}], "publish_date": "March 2003"}
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs["params"]["bibkeys"])
        return FakeLibrary({"ISBN:9780141439518": book})

    monkeypatch.setattr(citations.requests, "get", fake_get)
    ref = citations.lookup_isbn("978-0-14-143951-8", {"austen2003"})
    assert calls == ["ISBN:9780141439518"]
    assert (ref.kind, ref.title, ref.authors, ref.year, ref.container, ref.key) == (
        "book", "Pride and Prejudice: A Novel", ["Austen, Jane"], "2003", "Penguin Books", "austen2003a")
    assert format_entry(ref, "APA") == "Austen, J. (2003). *Pride and Prejudice: A Novel*. Penguin Books."


def test_lookup_isbn_not_found(monkeypatch):
    monkeypatch.setattr(citations.requests, "get", lambda url, **kwargs: FakeLibrary({}))
    with pytest.raises(CitationError, match="No book found"):
        citations.lookup_isbn("0-306-40615-2", set())


def test_in_text_styles():
    text = "A [@smith2020]. B [@lee2019; @ng2021]."
    assert insert_citations(text, REFS, "IEEE").text == "A [1]. B [2], [3]."
    assert insert_citations(text, REFS, "APA").text == "A (Smith, 2020). B (Lee & Park, 2019; Ng et al., 2021)."
    assert insert_citations(text, REFS, "Harvard").text == "A (Smith 2020). B (Lee and Park 2019; Ng et al. 2021)."
    assert insert_citations(text, REFS, "MLA").text == "A (Smith). B (Lee and Park; Ng et al.)."
    assert insert_citations(text, REFS, "Chicago").text == "A (Smith 2020). B (Lee and Park 2019; Ng et al. 2021)."


def test_chicago_entries():
    assert format_entry(ONE, "Chicago") == (
        "Smith, Jane. 2020. “Sleep and memory.” *Nature* 5 (2): 10-20. https://doi.org/10.1000/xyz."
    )
    assert format_entry(TWO, "Chicago") == "Lee, Anna, and Min Park. 2019. *Writing Well*. Penguin."
    assert format_entry(MANY, "Chicago") == "Ng, A, C Bo, and D Wu. 2021. “A web page.” Example. https://example.com."
    nobody = Reference(key="k", kind="web", title="Style guide", url="https://x.org")
    assert format_entry(nobody, "Chicago") == "“Style guide.” n.d. https://x.org."


def test_ieee_numbers_follow_first_use():
    r = insert_citations("X [@ng2021]. Y [@smith2020]. Z [@ng2021].", REFS, "IEEE")
    assert r.text == "X [1]. Y [2]. Z [1]."
    assert [x.key for x in r.used] == ["ng2021", "smith2020"]


def test_unknown_keys_left_alone_and_reported():
    r = insert_citations("A [@missing]. B [@smith2020; @gone].", REFS, "APA")
    assert r.text == "A [@missing]. B (Smith, 2020)."
    assert r.unknown == ["missing", "gone"]


def test_latex_output():
    r = insert_citations("A [@smith2020; @lee2019].", REFS, "IEEE")
    assert r.latex == "A \\cite{smith2020,lee2019}."


def test_reference_list_order():
    assert reference_list([MANY, ONE], "IEEE")[0].startswith("[1] A. Ng")
    apa = reference_list([MANY, ONE, TWO], "APA")
    assert [e.split(",")[0] for e in apa] == ["Lee", "Ng", "Smith"]


def test_entries():
    assert format_entry(ONE, "APA") == "Smith, J. (2020). Sleep and memory. *Nature*, *5*(2), 10-20. https://doi.org/10.1000/xyz"
    assert format_entry(ONE, "IEEE") == 'J. Smith, "Sleep and memory," *Nature*, vol. 5, no. 2, pp. 10-20, 2020, doi: 10.1000/xyz.'
    assert format_entry(TWO, "MLA") == "Lee, Anna, and Min Park. *Writing Well*. Penguin, 2019."
    assert format_entry(TWO, "Harvard") == "Lee, A. and Park, M. (2019) *Writing Well*. Penguin."
    assert "Available: https://example.com" in format_entry(MANY, "IEEE")


def test_make_key_unique():
    assert make_key(["Smith, Jane"], "2020", set()) == "smith2020"
    assert make_key(["Smith, Jane"], "2020", {"smith2020"}) == "smith2020a"
    assert make_key(["O'Brien, Pat"], "", set()) == "obrien"
    assert make_key([], "1999", set()) == "ref1999"


def test_bibtex():
    bib = to_bibtex([ONE, MANY])
    assert "@article{smith2020," in bib
    assert "pages = {10--20}" in bib
    assert "@misc{ng2021," in bib
    assert "author = {Ng, A and Bo, C and Wu, D}" in bib


def test_bibtex_escapes_specials():
    ref = Reference(key="k", kind="article", title="R&D at 50%", authors=[], container="A & B")
    bib = to_bibtex([ref])
    assert "R\\&D at 50\\%" in bib and "A \\& B" in bib


def test_csl_json_round_trip():
    back = from_csl_json(to_csl_json(REFS), set())
    assert [(r.key, r.kind, r.title, r.authors, r.year, r.container) for r in back] == [
        (r.key, r.kind, r.title, r.authors, r.year, r.container) for r in REFS
    ]


def test_csl_json_rekeys_duplicates_and_rejects_junk():
    data = json.dumps([{"id": "smith2020", "title": "T", "author": [{"family": "Smith", "given": "J"}], "issued": {"date-parts": [[2020]]}}])
    assert from_csl_json(data, {"smith2020"})[0].key == "smith2020a"
    with pytest.raises(CitationError):
        from_csl_json("not json", set())
    with pytest.raises(CitationError):
        from_csl_json('{"a": 1}', set())


def test_normalize_doi():
    assert normalize_doi("https://doi.org/10.1038/nature14539") == "10.1038/nature14539"
    assert normalize_doi(" doi: 10.1000/ABC ") == "10.1000/ABC"
    with pytest.raises(CitationError):
        normalize_doi("hello")


def test_from_crossref():
    msg = {
        "type": "journal-article", "title": ["Deep learning"], "container-title": ["Nature"],
        "author": [{"family": "LeCun", "given": "Yann"}, {"name": "Some Consortium"}],
        "issued": {"date-parts": [[2015, 5]]}, "volume": "521", "issue": "7553", "page": "436-444",
        "DOI": "10.1038/nature14539", "URL": "https://doi.org/10.1038/nature14539",
    }
    ref = from_crossref(msg, set())
    assert ref.key == "lecun2015" and ref.kind == "article"
    assert ref.authors == ["LeCun, Yann", "Some Consortium"]
    assert ref.container == "Nature" and ref.year == "2015"


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code, self.payload = status, payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


def test_lookup_doi_not_found(monkeypatch):
    monkeypatch.setattr(citations.requests, "get", lambda *a, **k: FakeResponse(404))
    with pytest.raises(CitationError, match="No record"):
        citations.lookup_doi("10.1000/none", set())


def test_lookup_doi_network_error(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError()

    monkeypatch.setattr(citations.requests, "get", boom)
    with pytest.raises(CitationError, match="reach Crossref"):
        citations.lookup_doi("10.1000/x", set())


def test_lookup_doi_success(monkeypatch):
    payload = {"message": {"type": "book", "title": ["A Book"], "publisher": "Pub", "author": [{"family": "Doe", "given": "J"}],
                           "issued": {"date-parts": [[2001]]}}}
    monkeypatch.setattr(citations.requests, "get", lambda *a, **k: FakeResponse(200, payload))
    ref = citations.lookup_doi("10.1000/book", set())
    assert ref.kind == "book" and ref.container == "Pub" and ref.key == "doe2001"
