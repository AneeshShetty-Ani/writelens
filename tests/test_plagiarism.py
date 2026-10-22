from plagiarism import check, is_cited, quick_check, sentence_bounds

SRC_A = "the committee reviewed every budget line before approving the final plan for next year"
SRC_B = "rising sea levels threaten coastal cities across the world within the next century"


def test_quick_check_ignores_case_and_punctuation():
    r = quick_check("The Cat, sat on THE mat!", "the cat sat on the mat")
    assert r.similarity == 1.0 and r.matched == r.total == 6


def test_quick_check_partial_and_spans():
    source = "one two three four five six"
    sub = "zero one two three four nine"
    r = quick_check(source, sub, n=4)
    assert (r.matched, r.total) == (4, 6)
    assert [sub[s:e] for s, e in r.spans_submission] == ["one two three four"]
    assert [source[s:e] for s, e in r.spans_source] == ["one two three four"]


def test_quick_check_strictness():
    source, sub = "alpha beta gamma delta", "x alpha beta gamma y"
    assert quick_check(source, sub, n=3).matched == 3
    assert quick_check(source, sub, n=4).matched == 0


def test_quick_check_empty():
    assert quick_check("", "text").similarity == 0


def test_uncited_match():
    draft = f"My essay starts here. {SRC_A}. Then my own ideas follow."
    r = check(draft, {"a.txt": SRC_A, "b.txt": SRC_B})
    assert len(r.matches) == 1
    m = r.matches[0]
    assert m.source == "a.txt" and not m.cited
    assert draft[m.start : m.end].lower() == SRC_A
    assert r.coverage == r.uncited_coverage > 0
    assert [s.name for s in r.sources] == ["a.txt", "b.txt"]
    assert r.sources[1].matches == 0


def test_cited_in_various_styles():
    for citation in ("[@smith2020]", "[3]", "(Smith, 2020)", "(Smith et al. 2020a)", "\\cite{smith}"):
        draft = f"Intro. {SRC_A} {citation}. End."
        r = check(draft, {"a": SRC_A})
        assert r.matches[0].cited, citation
        assert r.uncited_coverage == 0


def test_quoted_counts_as_cited():
    for q in ('"{}"', "“{}”"):
        draft = "As the report says, " + q.format(SRC_A) + " and that matters."
        assert check(draft, {"a": SRC_A}).matches[0].cited, q


def test_citation_in_other_sentence_does_not_count():
    draft = f"Earlier claim [@x]. {SRC_A}. Later."
    assert not check(draft, {"a": SRC_A}).matches[0].cited


def test_overlapping_sources_counted_once_in_coverage():
    draft = f"{SRC_A}."
    r = check(draft, {"a": SRC_A, "copy of a": SRC_A})
    assert len(r.matches) == 2
    assert r.coverage == 1.0


def test_both_sources_matched():
    draft = f"{SRC_A}. Something in between written by me here. {SRC_B}."
    r = check(draft, {"a": SRC_A, "b": SRC_B})
    assert {m.source for m in r.matches} == {"a", "b"}
    assert 0 < r.coverage < 1


def test_empty_draft():
    r = check("", {"a": SRC_A})
    assert r.words == 0 and r.matches == []


def test_is_cited_helper():
    text = "One. Two words here (Lee, 2019). Three."
    bounds = sentence_bounds(text)
    assert is_cited(text, 5, 14, bounds)
    assert not is_cited(text, 0, 3, bounds)
