from assignment import (
    check_assignment, check_length, check_quantities, coverage, improve_essay, question_topics,
)
from ui.assignment_page import EXAMPLE_ESSAY, EXAMPLE_QUESTION


def by_label(requirements):
    return {r.label: r for r in requirements}


def test_example_covers_most_requirements():
    found = by_label(check_assignment(EXAMPLE_QUESTION, EXAMPLE_ESSAY))
    assert found["Evaluate / assess"].status == "ok"
    assert found["3 sources"].status == "partial" and "2 different citations" in found["3 sources"].detail
    assert found["2 examples"].status == "ok"
    assert found["Conclusion"].status == "ok" and found["Introduction"].status == "ok"
    assert found["Reference list"].status == "ok"
    assert found["sleep"].status == "ok" and "paragraph" in found["sleep"].detail
    assert found["360–440 words"].status == "missing"


def test_missing_task_and_topic():
    found = by_label(check_assignment("Compare solar and wind energy.", "Solar panels are cheap now."))
    assert found["Compare / contrast"].status == "missing"
    assert found["solar"].status == "partial"
    assert found["wind"].status == "missing"
    assert found["energy"].status == "missing"


def test_word_counts_and_ranges():
    essay = " ".join(["word"] * 1000)
    assert check_length("Write 1,000 words.", essay)[0].status == "ok"
    assert check_length("A 1500-word essay.", essay)[0].detail == "you have 1,000: 350 short"
    assert check_length("Between 800 and 1200 words.", essay)[0].label == "800–1,200 words"
    assert check_length("800-1,200 words.", essay)[0].status == "ok"
    assert check_length("No length given.", essay) == []


def test_quantities_and_things_to_check_yourself():
    essay = "Bees matter (Smith, 2020). Bees pollinate [1]. For example, apples need bees."
    found = by_label(check_quantities("Give three reasons, using at least two sources and one example.", essay))
    assert found["3 reasons"].status == "check"
    assert found["2 sources"].status == "ok"
    assert found["1 examples"].status == "ok"


def test_topics_leave_out_instruction_words():
    topics = question_topics("Critically discuss the role of renewable energy in reducing students' carbon emissions. "
                             "Use three sources.")
    assert topics == ["role", "renewable", "energy", "reducing", "carbon", "emissions"]


def test_improved_version_marks_what_is_missing():
    question = ("Evaluate the impact of exercise on health. Use two sources. Include an introduction, a conclusion "
                "and a reference list.")
    essay = "Due to the fact that exercise strengthens the heart, people live longer (Smith, 2020)."
    improved, changes, notes = improve_essay(essay, check_assignment(question, essay))
    assert improved.startswith("[TO DO: add an introduction that says what the essay will argue]\n\nBecause exercise")
    assert ("(Smith, 2020). [TO DO: evaluate / assess: weigh strengths against limitations, e.g. “However, a "
            "limitation is ...”] [TO DO: add 1 more source, cited like (Author, Year)] [TO DO: say something about "
            "“impact”] [TO DO: say something about “health”]\n\n[TO DO: add a concluding paragraph that sums up your "
            "answer to the question]\n\nReferences\n\n[TO DO: list every source you cited, in your citation style]"
            ) in improved
    assert changes == [("due to the fact that", "because", 1)] and notes == 7


def test_improved_version_puts_notes_before_the_conclusion_and_keeps_references():
    found = check_assignment(EXAMPLE_QUESTION + " Discuss its cost.", EXAMPLE_ESSAY)
    improved, _, _ = improve_essay(EXAMPLE_ESSAY, found)
    body, conclusion = improved.split("\n\nOverall,")
    assert body.endswith("[TO DO: add 1 more source, cited like (Author, Year)] [TO DO: say something about “impact”] "
                         "[TO DO: say something about “cost”]")
    assert conclusion.endswith("References\n\nLee, A. (2020). Study groups online. Journal of Learning.\n"
                               "Smith, J. (2021). Phones at midnight. Sleep Studies.")


def test_improved_version_without_gaps_has_no_notes():
    essay = "Exercise improves health. Exercise also improves mood."
    assert improve_essay(essay, check_assignment("Exercise and health.", essay)) == (essay, [], 0)


def test_coverage_skips_check_yourself():
    reqs = check_assignment("Give two reasons why exercise improves health.", "Exercise improves health because "
                            "it strengthens the heart. Therefore, people live longer.")
    met, total = coverage(reqs)
    assert total == len([r for r in reqs if r.status != "check"]) and met <= total
