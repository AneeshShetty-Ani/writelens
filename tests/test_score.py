from analysis import Report, analyze, grade_label
from nlp_checks import NlpReport
from score import score_label, writing_score


def test_clean_text_scores_high():
    r = analyze("Cats chase mice. Dogs chase cats. Birds sing in the morning.")
    assert writing_score(r, NlpReport()) >= 85


def test_issues_lower_the_score():
    r = Report(words=100, sentences=5, reading_ease=65)
    clean = writing_score(r, NlpReport())
    messy = writing_score(r, NlpReport(passive=["a", "b", "c"], adverbs=[("really", 4)]))
    assert messy < clean


def test_score_is_per_word_count():
    nlp = NlpReport(passive=["a", "b"])
    short = writing_score(Report(words=100, reading_ease=65), nlp)
    long = writing_score(Report(words=1000, reading_ease=65), nlp)
    assert long > short


def test_score_stays_in_range():
    nlp = NlpReport(passive=["x"] * 200)
    assert writing_score(Report(words=60, reading_ease=10), nlp) == 0
    assert writing_score(Report(), NlpReport()) == 0


def test_labels():
    assert score_label(90) == "Excellent" and score_label(40) == "Hard to read"
    assert grade_label(3) == "Very easy" and grade_label(10) == "High school"


def test_grade_level_rises_with_harder_text():
    easy = analyze("The cat sat. The dog ran. We had fun.")
    hard = analyze("Institutional considerations necessitate comprehensive reevaluation of organisational methodologies.")
    assert hard.grade_level > easy.grade_level
