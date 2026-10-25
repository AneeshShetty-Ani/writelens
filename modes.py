"""Writing modes: which checks matter for the kind of text being written. An email can say "you" and
"don't"; a lab report is expected to use the passive voice."""

from dataclasses import replace

from analysis import Report
from nlp_checks import NlpReport

DEFAULT_MODE = "Essay"
# mode -> (description, issue kinds (keys of score.WEIGHTS) that aren't flagged in it)
MODES = {
    "Essay": ("Essays and assignments: every check.", set()),
    "Report": ("Lab and technical reports: the passive voice is normal there, so it isn't flagged.", {"passive"}),
    "Email": ("Emails and messages: contractions, “you” and essay openings and endings are fine.",
              {"contraction", "second_person", "weak_opening", "weak_ending"}),
    "Casual": ("Blogs, stories and posts: contractions, “you”, informal words and essay structure are fine.",
               {"contraction", "second_person", "informal", "weak_opening", "weak_ending"}),
}
# issue kind -> (Report field, its empty value)
REPORT_FIELDS = {
    "contraction": ("contractions", []),
    "second_person": ("second_person", 0),
    "informal": ("informal", []),
    "weak_opening": ("weak_openings", []),
    "weak_ending": ("ending_issues", []),
}
# issue kind -> highlight category (see highlight.LABELS)
SPAN_CATEGORIES = {"passive": "passive", "contraction": "contraction", "informal": "informal", "weak_opening": "opening"}


def ignored(mode: str) -> set[str]:
    return MODES.get(mode, MODES[DEFAULT_MODE])[1]


def apply_mode(report: Report, nlp: NlpReport, mode: str) -> tuple[Report, NlpReport]:
    """Copies of the results with the checks this mode doesn't use emptied, so the score, cards,
    highlights and reports all leave them out."""
    skip = ignored(mode)
    report = replace(report, **{REPORT_FIELDS[k][0]: REPORT_FIELDS[k][1] for k in skip if k in REPORT_FIELDS})
    if "passive" in skip:
        nlp = replace(nlp, passive=[])
    return report, nlp


def hidden_spans(mode: str) -> set[str]:
    return {SPAN_CATEGORIES[k] for k in ignored(mode) if k in SPAN_CATEGORIES}
