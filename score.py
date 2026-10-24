"""One 0-100 writing score from the analysis results, so a draft can be compared with its next version."""

from analysis import Report
from nlp_checks import NlpReport

# points taken off per occurrence of each kind of issue
WEIGHTS = {"passive": 3, "wordy": 2, "long": 4, "cliche": 2, "adverb": 1, "weak_verb": 1, "repeated": 1,
           "contraction": 1, "mixed_spelling": 1}
PER_WORDS = 100  # issues are counted per this many words, so long texts aren't punished for length
MIN_WORDS = 50   # a 10-word text with one issue shouldn't drop to zero


# issue kind -> (singular, plural), for "Fixed: 2 passive sentences"
ISSUE_NAMES = {
    "passive": ("passive sentence", "passive sentences"),
    "wordy": ("wordy phrase", "wordy phrases"),
    "long": ("long sentence", "long sentences"),
    "cliche": ("cliché", "clichés"),
    "adverb": ("filler adverb", "filler adverbs"),
    "weak_verb": ("weak verb", "weak verbs"),
    "repeated": ("repeated word", "repeated words"),
    "contraction": ("contraction", "contractions"),
    "mixed_spelling": ("mixed spelling", "mixed spellings"),
}


def issue_counts(report: Report, nlp: NlpReport) -> dict[str, int]:
    """How many of each kind of issue the text has (keys of WEIGHTS)."""
    return {
        "passive": len(nlp.passive),
        "wordy": sum(hits for _, _, hits in report.wordy),
        "long": len(report.long_sentences),
        "cliche": sum(n for _, n in report.cliches),
        "adverb": sum(n for _, n in nlp.adverbs),
        "weak_verb": sum(n for _, n in nlp.weak_verbs),
        "repeated": len(nlp.repeated),
        "contraction": sum(n for _, n in report.contractions),
        "mixed_spelling": sum(n for _, n in report.minority_spelling),
    }


def issue_points(report: Report, nlp: NlpReport) -> int:
    return sum(WEIGHTS[kind] * n for kind, n in issue_counts(report, nlp).items())


def describe_counts(counts: dict[str, int]) -> str:
    """{"passive": 2, "cliche": 1} -> "2 passive sentences, 1 cliché"."""
    return ", ".join(f"{n} {ISSUE_NAMES[k][n != 1]}" for k, n in counts.items() if n)


def compare_drafts(before: dict[str, int], after: dict[str, int]) -> tuple[dict[str, int], dict[str, int]]:
    """(issues fixed, new issues) between two drafts' issue_counts()."""
    fixed = {k: before.get(k, 0) - n for k, n in after.items() if before.get(k, 0) > n}
    new = {k: n - before.get(k, 0) for k, n in after.items() if n > before.get(k, 0)}
    return fixed, new


def writing_score(report: Report, nlp: NlpReport) -> int:
    if not report.words:
        return 0
    density = issue_points(report, nlp) * PER_WORDS / max(report.words, MIN_WORDS)
    score = 100 - 1.5 * density
    if report.reading_ease < 30:
        score -= 10
    elif report.reading_ease < 50:
        score -= 5
    return round(min(100, max(0, score)))


def score_label(score: int) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 50:
        return "Needs work"
    return "Hard to read"
