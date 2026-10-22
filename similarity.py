"""Compare two documents: n-gram overlap, winnowing fingerprints, word-frequency cosine,
and the passages they share."""

import difflib
import math
import re
import zlib
from collections import Counter
from dataclasses import dataclass, field

TOKEN = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")
NGRAM = 5  # words per n-gram for the overlap scores
WINDOW = 4  # winnowing window, in n-grams
MATCH_WORDS = 7  # shortest shared run reported as a matching passage
MAX_WORDS = 50_000
SEQUENCE_MAX_WORDS = 5_000  # difflib can be slow on long texts, so it only sees the start
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "in", "is", "it",
    "its", "of", "on", "or", "that", "the", "this", "to", "was", "were", "which", "with",
}


@dataclass
class Token:
    word: str
    start: int
    end: int


@dataclass
class SimilarityReport:
    words_a: int = 0
    words_b: int = 0
    coverage_a: float = 0.0  # share of A's words inside passages also found in B
    coverage_b: float = 0.0
    ngram_jaccard: float = 0.0
    fingerprint_match: float = 0.0
    cosine: float = 0.0
    sequence_ratio: float = 0.0
    spans_a: list[tuple[int, int]] = field(default_factory=list)  # character spans
    spans_b: list[tuple[int, int]] = field(default_factory=list)
    passages: list[str] = field(default_factory=list)  # matched text, as it appears in A


def tokenize(text: str) -> list[Token]:
    return [Token(m.group().lower(), m.start(), m.end()) for m in TOKEN.finditer(text)][:MAX_WORDS]


def ngrams(words: list[str], n: int) -> list[tuple[str, ...]]:
    return [tuple(words[i : i + n]) for i in range(len(words) - n + 1)]


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def fingerprints(words: list[str]) -> set[int]:
    """Winnowing: hash every n-gram, keep the minimum hash of each sliding window."""
    hashes = [zlib.crc32(" ".join(g).encode()) for g in ngrams(words, NGRAM)]
    if len(hashes) <= WINDOW:
        return set(hashes)
    return {min(hashes[i : i + WINDOW]) for i in range(len(hashes) - WINDOW + 1)}


def cosine(words_a: list[str], words_b: list[str]) -> float:
    ca = Counter(w for w in words_a if w not in STOPWORDS)
    cb = Counter(w for w in words_b if w not in STOPWORDS)
    dot = sum(n * cb[w] for w, n in ca.items())
    norm = math.sqrt(sum(n * n for n in ca.values())) * math.sqrt(sum(n * n for n in cb.values()))
    return dot / norm if norm else 0.0


def sequence_ratio(words_a: list[str], words_b: list[str]) -> float:
    """difflib's ratio over word lists: 1.0 for identical texts. Only counts matches that
    appear in the same order in both, so it drops when paragraphs are moved around."""
    a, b = words_a[:SEQUENCE_MAX_WORDS], words_b[:SEQUENCE_MAX_WORDS]
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if a and b else 0.0


def shared_runs(tokens: list[Token], other: set[tuple[str, ...]], n: int = MATCH_WORDS) -> list[tuple[int, int]]:
    """Token index ranges [start, end) covered by n-grams that also occur in `other`
    (which must hold n-grams of the same size). Works in any order, so moved paragraphs are still found."""
    words = [t.word for t in tokens]
    covered = [False] * len(words)
    for i, gram in enumerate(ngrams(words, n)):
        if gram in other:
            covered[i : i + n] = [True] * n
    runs, start = [], None
    for i, c in enumerate(covered + [False]):
        if c and start is None:
            start = i
        elif not c and start is not None:
            runs.append((start, i))
            start = None
    return runs


def merge_runs(runs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for s, e in sorted(runs):
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(e, merged[-1][1]))
        else:
            merged.append((s, e))
    return merged


def compare(text_a: str, text_b: str) -> SimilarityReport:
    ta, tb = tokenize(text_a), tokenize(text_b)
    wa, wb = [t.word for t in ta], [t.word for t in tb]
    report = SimilarityReport(words_a=len(wa), words_b=len(wb))
    if not wa or not wb:
        return report

    report.ngram_jaccard = jaccard(set(ngrams(wa, NGRAM)), set(ngrams(wb, NGRAM)))
    fa, fb = fingerprints(wa), fingerprints(wb)
    report.fingerprint_match = len(fa & fb) / min(len(fa), len(fb)) if fa and fb else 0.0
    report.cosine = cosine(wa, wb)
    report.sequence_ratio = sequence_ratio(wa, wb)

    runs_a = shared_runs(ta, set(ngrams(wb, MATCH_WORDS)))
    runs_b = shared_runs(tb, set(ngrams(wa, MATCH_WORDS)))
    report.coverage_a = sum(e - s for s, e in runs_a) / len(wa)
    report.coverage_b = sum(e - s for s, e in runs_b) / len(wb)
    report.spans_a = [(ta[s].start, ta[e - 1].end) for s, e in runs_a]
    report.spans_b = [(tb[s].start, tb[e - 1].end) for s, e in runs_b]
    report.passages = [text_a[s:e] for s, e in report.spans_a]
    return report
