from analysis import analyze
from nlp_checks import NlpReport, check
from report import build_markdown


def test_report_contains_stats_and_findings():
    text = "The report was written by the team. Due to the fact that it rained, we stayed."
    md = build_markdown(analyze(text), check(text), "essay.docx")
    assert "**Source:** essay.docx" in md
    assert "| Words |" in md
    assert "### Passive voice" in md
    assert "The report was written by the team." in md
    assert "due to the fact that" in md


def test_report_clean_text():
    text = "Cats chase mice."
    md = build_markdown(analyze(text), check(text))
    assert "No issues found." in md
    assert "###" not in md


def test_report_notes_missing_spacy():
    md = build_markdown(analyze("Cats chase mice."), NlpReport(available=False))
    assert "unavailable" in md
