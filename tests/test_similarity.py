from similarity import MATCH_WORDS, compare, fingerprints, tokenize

SHARED = "the committee reviewed every budget line before approving the final plan for next year"


def test_identical_documents():
    r = compare(SHARED, SHARED)
    assert r.coverage_a == r.coverage_b == 1.0
    assert r.ngram_jaccard == 1.0 and r.fingerprint_match == 1.0
    assert round(r.cosine, 6) == 1.0


def test_sequence_ratio_drops_when_reordered():
    first, second = SHARED, "rising sea levels threaten coastal cities across the world within the next century"
    same = compare(f"{first}. {second}.", f"{first}. {second}.")
    moved = compare(f"{first}. {second}.", f"{second}. {first}.")
    assert same.sequence_ratio == 1.0
    assert moved.sequence_ratio < 1.0
    assert moved.coverage_a == 1.0  # the n-gram passages still find everything


def test_unrelated_documents():
    r = compare("Cats chase mice in the garden every morning.", "Quantum computers use qubits for calculations.")
    assert r.coverage_a == 0 and r.passages == []
    assert r.ngram_jaccard == 0


def test_shared_passage_found_even_when_moved():
    a = f"Opening sentence for A. {SHARED}. Closing words."
    b = f"Something else first. More filler text here. {SHARED.upper()}!"
    r = compare(a, b)
    assert len(r.passages) == 1
    assert r.passages[0].lower() == SHARED
    s, e = r.spans_b[0]
    assert b[s:e].lower() == SHARED


def test_short_overlap_is_not_a_passage():
    words = " ".join(f"w{i}" for i in range(MATCH_WORDS - 1))
    r = compare(f"{words} alpha", f"{words} beta")
    assert r.passages == []


def test_empty_input():
    r = compare("", "text")
    assert r.words_a == 0 and r.coverage_a == 0


def test_tokenize_keeps_offsets():
    toks = tokenize("Don't stop, now!")
    assert [t.word for t in toks] == ["don't", "stop", "now"]
    assert toks[1].start == 6 and toks[1].end == 10


def test_fingerprints_short_text():
    assert fingerprints(["a", "b"]) == set()
    assert len(fingerprints("a b c d e".split())) == 1
