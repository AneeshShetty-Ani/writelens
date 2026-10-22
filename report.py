"""Build a downloadable Markdown report from the analysis results."""

from datetime import date

from analysis import LONG_SENTENCE_WORDS, Report
from nlp_checks import REPEAT_MIN, NlpReport


def build_markdown(report: Report, nlp: NlpReport, source: str = "Pasted text") -> str:
    lines = [
        "# WriteLens report",
        "",
        f"**Source:** {source}  ",
        f"**Date:** {date.today().isoformat()}",
        "",
        "## Stats",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Words | {report.words} |",
        f"| Sentences | {report.sentences} |",
        f"| Avg sentence length | {report.avg_sentence_len:.1f} |",
        f"| Reading ease (Flesch) | {report.reading_ease:.0f} |",
        "",
        "## Suggestions",
        "",
    ]

    sections = 0

    def section(title: str, items: list[str]) -> None:
        nonlocal sections
        if items:
            sections += 1
            lines.extend([f"### {title}", "", *items, ""])

    section("Wordy phrases", [f"- “{p}” ×{n} → consider {s}" for p, s, n in report.wordy])
    section(f"Long sentences (over {LONG_SENTENCE_WORDS} words)", [f"- {s}" for s in report.long_sentences])
    section("Passive voice", [f"- {s}" for s in nlp.passive])
    section(f"Repeated words ({REPEAT_MIN}+ uses)", [f"- {w} ×{n}" for w, n in nlp.repeated])
    section("Weak verbs", [f"- {w} ×{n}" for w, n in nlp.weak_verbs])
    section("Filler adverbs", [f"- {w} ×{n}" for w, n in nlp.adverbs])

    if not nlp.available:
        lines.extend(["_Grammar checks were unavailable (spaCy model not installed)._", ""])
    if sections == 0:
        lines.extend(["No issues found.", ""])
    return "\n".join(lines)
