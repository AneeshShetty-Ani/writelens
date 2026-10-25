from analysis import analyze
from modes import MODES, apply_mode, hidden_spans
from nlp_checks import NlpReport
from score import WEIGHTS, writing_score

TEXT = "In today's world, you don't know. You are gonna love it. You can try it. The report was written by us."


def test_every_mode_ignores_real_issue_kinds():
    for desc, skip in MODES.values():
        assert desc and skip <= set(WEIGHTS)


def test_essay_mode_keeps_everything():
    report, nlp = apply_mode(analyze(TEXT), NlpReport(passive=["The report was written by us."]), "Essay")
    assert report.contractions and report.informal and report.second_person and report.weak_openings
    assert nlp.passive


def test_casual_mode_drops_formal_checks():
    full = analyze(TEXT)
    report, nlp = apply_mode(full, NlpReport(passive=["x"]), "Casual")
    assert not report.contractions and not report.informal and not report.second_person and not report.weak_openings
    assert nlp.passive == ["x"]  # passive still matters in a blog
    assert full.contractions  # the original isn't changed
    assert writing_score(report, nlp) > writing_score(full, nlp)


def test_report_mode_allows_passive_and_unknown_mode_is_essay():
    _, nlp = apply_mode(analyze(TEXT), NlpReport(passive=["x"]), "Report")
    assert nlp.passive == []
    report, _ = apply_mode(analyze(TEXT), NlpReport(), "Nonsense")
    assert report.contractions


def test_hidden_spans():
    assert hidden_spans("Essay") == set()
    assert hidden_spans("Report") == {"passive"}
    assert hidden_spans("Casual") == {"contraction", "informal", "opening"}
