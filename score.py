"""One 0-100 writing score from the analysis results, so a draft can be compared with its next version."""

from analysis import Report
from nlp_checks import NlpReport

# points taken off per occurrence of each kind of issue
WEIGHTS = {"passive": 3, "wordy": 2, "long": 4, "adverb": 1, "weak_verb": 1, "repeated": 1}
PER_WORDS = 100  # issues are counted per this many words, so long texts aren't punished for length
MIN_WORDS = 50   # a 10-word text with one issue shouldn't drop to zero


def issue_points(report: Report, nlp: NlpReport) -> int:
    return (
        WEIGHTS["passive"] * len(nlp.passive)
        + WEIGHTS["wordy"] * sum(hits for _, _, hits in report.wordy)
        + WEIGHTS["long"] * len(report.long_sentences)
        + WEIGHTS["adverb"] * sum(n for _, n in nlp.adverbs)
        + WEIGHTS["weak_verb"] * sum(n for _, n in nlp.weak_verbs)
        + WEIGHTS["repeated"] * len(nlp.repeated)
    )


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
