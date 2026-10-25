from analysis import opening_span, paragraph_spans, split_paragraphs
from structure import key_words, outline, sentence_effort, stem, word_budget

ESSAY = """Introduction

Social media is part of daily life for students. This essay looks at its effect on sleep.

Phones keep students awake. Many students scroll late at night, and late scrolling means less sleep before class.

Group chats also help students share notes and plan revision together, which can raise marks.

Overall, social media costs sleep but can help study when it is used with limits.
"""


def test_paragraphs_skip_headings():
    paragraphs = split_paragraphs(ESSAY)
    assert len(paragraphs) == 4
    assert paragraphs[0].startswith("Social media is part")
    assert ESSAY[slice(*opening_span(ESSAY))] == paragraphs[0]


def test_paragraphs_stop_at_the_reference_list():
    text = ESSAY + "\nReferences\n\nSmith, J. (2021). Phones at midnight and how they keep us up. Sleep Studies."
    assert split_paragraphs(text) == split_paragraphs(ESSAY)


def test_paragraphs_split_on_single_line_breaks_when_no_blank_lines():
    text = "First paragraph with enough words to count here.\nSecond paragraph also has enough words to count."
    assert len(paragraph_spans(text)) == 2


def test_single_paragraph_opening_is_first_three_sentences():
    text = "One. Two. Three. Four."
    assert text[slice(*opening_span(text))] == "One. Two. Three."


def test_stem_joins_word_forms():
    assert stem("studies") == stem("study")
    assert stem("changes") == stem("change")
    assert stem("teachers") == stem("teacher")


def test_key_words_most_used_first():
    assert key_words("Bees make honey. Bees love flowers. Flowers feed bees.") == ["bees", "flowers"]
    assert key_words("Nothing repeats in this particular line.") == ["particular", "nothing"]


def test_outline_points_and_notes():
    points = outline(ESSAY)
    assert [p.number for p in points] == [1, 2, 3, 4]
    assert points[1].main_point == "Phones keep students awake."
    assert "students" in points[1].key_words
    assert any("only one sentence" in n for n in points[2].notes)


def test_outline_flags_similar_paragraphs():
    para = ("Electric cars cut pollution in cities because electric cars burn no petrol, and electric motors "
            "are quiet, so cities with electric cars have cleaner air and less pollution overall.")
    text = f"{para}\n\nA different topic entirely about gardens.\n\n{para.replace('Electric cars cut', 'Electric cars reduce')}"
    points = outline(text)
    assert any("paragraph 3" in n for n in points[0].notes)
    assert any("paragraph 1" in n for n in points[2].notes)


def test_word_budget():
    budget = word_budget(ESSAY)
    assert (budget.intro, budget.body, budget.conclusion) == (17, 33, 15)
    assert budget.total == 65
    lopsided = word_budget(" ".join(["Intro words."] * 40) + "\n\nBody point here.\n\nThe end.")
    assert any("introduction is" in a for a in lopsided.advice)
    assert any("conclusion is only" in a for a in lopsided.advice)
    assert word_budget("Just one paragraph here.") is None


def test_sentence_effort_levels():
    long_hard = ("The institutional reorganisation necessitated comprehensive evaluation of administrative "
                 "methodologies, considerable consultation with representatives, and additional documentation "
                 "regarding operational responsibilities everywhere.")
    text = f"Cats sit on mats. {long_hard}"
    efforts = sentence_effort(text)
    assert [e.level for e in efforts] == ["easy", "hard"]
    passive = sentence_effort("The ball was kicked by the boy.", ["The ball was kicked by the boy."])
    assert passive[0].score > sentence_effort("The boy kicked the ball today.")[0].score
    assert sentence_effort("Introduction") == []  # headings aren't sentences to judge
