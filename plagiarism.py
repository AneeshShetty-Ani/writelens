"""Check a draft against many sources: which passages match which source, and whether each
match is quoted or cited."""

import re
from dataclasses import dataclass, field

from analysis import split_sentences
from similarity import MATCH_WORDS, merge_runs, ngrams, sequence_ratio, shared_runs, tokenize

MAX_SOURCES = 25
# [@key], \cite{key}, [1] / [1, 2] / [1-3], or (Author, 2020) / (Author et al. 2020a)
CITATION = re.compile(
    r"\[@[\w:-]+|\\cite\w*\{|\[\d+(?:\s*[,–-]\s*\d+)*\]|\([^()]*\b(?:1[5-9]|20)\d{2}[a-z]?\b[^()]*\)"
)


@dataclass
class Match:
    start: int  # character offsets in the draft
    end: int
    source: str
    cited: bool  # inside quotation marks, or its sentence carries a citation


@dataclass
class SourceResult:
    name: str
    words: int
    coverage: float  # share of the draft's words matched to this source
    matches: int


@dataclass
class PlagiarismReport:
    words: int = 0
    coverage: float = 0.0  # share of the draft's words matched to any source
    uncited_coverage: float = 0.0
    sources: list[SourceResult] = field(default_factory=list)
    matches: list[Match] = field(default_factory=list)


@dataclass
class QuickResult:
    similarity: float = 0.0  # share of the submission's words that match the source
    matched: int = 0
    total: int = 0
    sequence_ratio: float = 0.0  # difflib, for a second opinion
    spans_source: list[tuple[int, int]] = field(default_factory=list)
    spans_submission: list[tuple[int, int]] = field(default_factory=list)


def quick_check(source: str, submission: str, n: int = 4) -> QuickResult:
    """One source vs one submission. Text is lower-cased and punctuation ignored; a word counts as
    matched when it sits inside an n-word sequence that also appears in the other text."""
    ts, tb = tokenize(source), tokenize(submission)
    result = QuickResult(total=len(tb))
    if not ts or not tb:
        return result
    runs_b = shared_runs(tb, set(ngrams([t.word for t in ts], n)), n)
    runs_s = shared_runs(ts, set(ngrams([t.word for t in tb], n)), n)
    result.matched = sum(e - s for s, e in runs_b)
    result.similarity = result.matched / len(tb)
    result.sequence_ratio = sequence_ratio([t.word for t in ts], [t.word for t in tb])
    result.spans_submission = [(tb[s].start, tb[e - 1].end) for s, e in runs_b]
    result.spans_source = [(ts[s].start, ts[e - 1].end) for s, e in runs_s]
    return result


def quote_and_cite(text: str, passages: list[tuple[int, int, str]]) -> str:
    """Put each (start, end, citation) passage in quotation marks followed by its citation, so copied
    words are credited. Passages already inside quotes, or overlapping an earlier one, are left alone."""
    out, pos = [], 0
    for start, end, cite in sorted(passages):
        if start < pos or text[start - 1 : start] in ('"', "“"):
            continue
        out.append(text[pos:start] + f'"{text[start:end]}"' + (f" {cite}" if cite else ""))
        pos = end
    return "".join(out) + text[pos:]


def sentence_bounds(text: str) -> list[tuple[int, int]]:
    bounds, pos = [], 0
    for s in split_sentences(text):
        start = text.find(s, pos)
        if start >= 0:
            pos = start + len(s)
            bounds.append((start, pos))
    return bounds


def is_quoted(text: str, start: int, end: int, sentence_start: int) -> bool:
    before = text[sentence_start:start]
    straight_open = before.count('"') % 2 == 1
    curly_open = before.count("“") > before.count("”")
    after = text[end : end + 3]
    return (straight_open and '"' in after) or (curly_open and "”" in after)


def is_cited(text: str, start: int, end: int, bounds: list[tuple[int, int]]) -> bool:
    # The citation may sit in any sentence the passage touches.
    touched = [(s, e) for s, e in bounds if s < end and e > start] or [(start, end)]
    first, last = touched[0][0], touched[-1][1]
    return bool(CITATION.search(text, first, last + 1)) or is_quoted(text, start, end, first)


def check(draft: str, sources: dict[str, str]) -> PlagiarismReport:
    tokens = tokenize(draft)
    report = PlagiarismReport(words=len(tokens))
    if not tokens:
        return report

    bounds = sentence_bounds(draft)
    all_runs, uncited_runs = [], []
    for name, text in list(sources.items())[:MAX_SOURCES]:
        source_words = [t.word for t in tokenize(text)]
        runs = shared_runs(tokens, set(ngrams(source_words, MATCH_WORDS)))
        report.sources.append(
            SourceResult(name, len(source_words), sum(e - s for s, e in runs) / len(tokens), len(runs))
        )
        for s, e in runs:
            start, end = tokens[s].start, tokens[e - 1].end
            cited = is_cited(draft, start, end, bounds)
            report.matches.append(Match(start, end, name, cited))
            all_runs.append((s, e))
            if not cited:
                uncited_runs.append((s, e))

    report.coverage = sum(e - s for s, e in merge_runs(all_runs)) / len(tokens)
    report.uncited_coverage = sum(e - s for s, e in merge_runs(uncited_runs)) / len(tokens)
    report.sources.sort(key=lambda r: r.coverage, reverse=True)
    report.matches.sort(key=lambda m: (m.start, m.source))
    return report
