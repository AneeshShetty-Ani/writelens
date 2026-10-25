from ai_tasks import (
    AssignmentReview, Judgement, accept_assignment, accept_citation, accept_feedback, accept_plagiarism,
    accept_web_details, accept_writing, assignment_task, citation_task, combine_assignment, combine_plagiarism,
    combine_writing, feedback_task, find_quote, merge_assignment, parts, plagiarism_parts, plagiarism_task,
    web_details_task, writing_task,
)
from assignment import Requirement

TEXT = "Phones keeps students awake. Many students scroll late at night, so they sleeps less before class."


def test_find_quote_ignores_case_and_spacing():
    assert find_quote(TEXT, "phones  KEEPS students") == (0, 21)
    assert find_quote(TEXT, "not in the text") is None
    assert find_quote("the theme", "he") is None  # whole words only
    assert find_quote(TEXT, "") is None


def test_writing_review_keeps_only_real_quotes_and_a_fair_rewrite():
    accept = accept_writing(TEXT)
    review = accept({
        "issues": [{"quote": "Phones keeps students", "problem": "Subject and verb don't agree.", "fix": "Use “keep”."},
                   {"quote": "words the AI made up", "problem": "Invented.", "fix": "-"}],
        "improved": "Phones keep students awake. Many students scroll late at night, so they sleep less before class.",
    })
    assert [i.quote for i in review.issues] == ["Phones keeps students"]
    assert review.issues[0].start == 0 and review.improved.startswith("Phones keep students")
    assert accept({"issues": [], "improved": "Too short."}).improved == ""  # it changed the length too much
    assert accept({"improved": "no issues list"}) is None


def test_parts_cut_at_paragraphs_and_cover_the_whole_text():
    paragraphs = [f"Paragraph {i}" + " word" * 300 for i in range(12)]
    text = "\n\n".join(paragraphs)
    spans = parts(text, 4000)
    assert len(spans) > 1 and all(e - s <= 4000 for s, e in spans)
    assert all(text[s:e].startswith("Paragraph") for s, e in spans)  # each part starts a paragraph
    assert "\n\n".join(text[s:e] for s, e in spans) == text  # nothing is lost between parts
    assert parts("short text") == [(0, 10)] and parts("   ") == []
    assert [e - s for s, e in parts("x" * 25, 10)] == [10, 10, 5]  # no break anywhere: hard cut


def test_long_writing_is_reviewed_in_parts_and_put_back_together():
    text = "First part has errors.\n\nSecond part is fine."
    spans = [(0, 22), (24, 44)]
    first = accept_writing(text[0:22])({"issues": [{"quote": "has errors", "problem": "Vague.", "fix": "Say which."}],
                                        "improved": "The first part has errors."})
    second = accept_writing(text[24:44])({"issues": [{"quote": "is fine", "problem": "Weak.", "fix": "Be specific."}],
                                          "improved": ""})  # the rewrite failed its check
    review = combine_writing(text, spans, [first, second], lambda part: part.upper())
    assert [text[i.start:i.end] for i in review.issues] == ["has errors", "is fine"]  # placed in the whole text
    assert review.improved == "The first part has errors.\n\nSECOND PART IS FINE." and review.offline_parts == 1
    assert combine_writing(text, spans, [None, None], str.upper).improved == ""  # nothing from the AI
    assert writing_task("word " * 3000)[1] == 900 + 15000 // 3  # long parts still get a rewrite


def test_assignment_judgements_merge_into_the_checklist():
    reqs = [Requirement("Task", "Evaluate / assess", "missing", "no signs", "evaluate: ..."),
            Requirement("Length", "400–440 words", "missing", "you have 100: 300 short"),
            Requirement("Structure", "Conclusion", "partial", "...", "make it sum up", "last")]
    task, _ = assignment_task("Evaluate X. 420 words.", "Essay.", reqs)
    assert "0. Evaluate / assess" in task and "400–440 words" not in task  # word counts stay exact
    review = accept_assignment(reqs)({
        "requirements": [{"id": 0, "status": "ok", "reason": "Paragraph 3 weighs both sides."},
                         {"id": 1, "status": "ok", "reason": "not allowed"},
                         {"id": 2, "status": "missing", "reason": "No summary.", "hint": "Add a closing summary."}],
        "extra": [{"label": "Use UK case law", "status": "partial", "reason": "One.", "hint": "Add another."},
                  {"label": "Bad status", "status": "great"},
                  {"label": "Three academic sources", "status": "missing"},  # counted offline already
                  {"label": "A strong conclusion", "status": "ok"}],  # already on the list
    })
    merged = merge_assignment(reqs, review, Requirement)
    assert [(r.label, r.status) for r in merged] == [("Evaluate / assess", "ok"), ("400–440 words", "missing"),
                                                     ("Conclusion", "missing"), ("Use UK case law", "partial")]
    assert merged[0].todo == "" and merged[2].todo == "conclusion: Add a closing summary." and merged[2].place == "last"
    assert accept_assignment(reqs)({"requirements": [{"id": 0, "status": "maybe"}]}) is None


def test_essay_parts_combine_with_the_best_status():
    ok, partial, missing = Judgement("ok", "Para 5.", ""), Judgement("partial", "Thin.", "Add more."), \
        Judgement("missing", "None.", "Add it.")
    review = combine_assignment([AssignmentReview({0: missing, 1: partial}, [("Use case law", missing)]), None,
                                 AssignmentReview({0: ok, 1: missing}, [("use case law", partial)])])
    assert review.judged == {0: ok, 1: partial}  # met in any part = met
    assert review.extra == [("use case law", partial)]
    assert "part 2 of 3 of the essay" in assignment_task("Q", "E", [], (2, 3))[0]
    assert "part 1 of 1" not in assignment_task("Q", "E", [])[0]


def test_long_plagiarism_checks_compare_every_part_with_every_source():
    draft = "\n\n".join(f"Draft paragraph {i}. " + "text " * 400 for i in range(6))  # about 12,000 characters
    sources = {"A": "alpha " * 5000, "B": "beta " * 100}  # 30,000 + 500 characters
    jobs = plagiarism_parts(sources, draft)
    draft_parts = {span for span, _ in jobs}
    assert len(draft_parts) == 2 and len(jobs) == 2 * len({tuple(g) for _, g in jobs})
    assert all(sum(map(len, g.values())) <= 40_000 for _, g in jobs)
    # paraphrases found in the second draft part are placed in the whole draft
    (start, end), group = sorted(draft_parts)[1], jobs[-1][1]
    piece = draft[start:end]
    quote = " ".join(piece.split()[:5])  # "Draft paragraph 3. text text"
    found = accept_plagiarism({"A": "alpha alpha"}, piece)({"paraphrases": [
        {"draft": quote, "source": "A", "source_quote": "alpha alpha", "why": "Same."}]})
    combined = combine_plagiarism([((start, end), group)], [found])
    assert combined[0].start == start and draft[combined[0].start:combined[0].end] == quote


def test_web_details_must_be_printed_on_the_page():
    page = "Bees and colour. By Jane Smith. Published 3 March 2021. Bees see ultraviolet light."
    assert "Bees and colour" in web_details_task("Bees and colour", page)[0]
    found = accept_web_details(page)({"authors": ["Jane Smith", "John Made-Up"], "year": "2021"})
    assert found == {"authors": ["Smith, Jane"], "year": "2021"}
    assert accept_web_details(page)({"authors": [], "year": "2019"}) == {"authors": [], "year": ""}
    assert accept_web_details(page)({"year": "2021"}) is None


def test_feedback_tidy_keeps_to_what_was_written():
    title, text = "app brokn", "when i press analyse on a pdf nothing happens it just spins"
    assert "Bug report" in feedback_task("Bug report", title, text)[0]
    accept = accept_feedback(title, text)
    tidy = accept({"title": "Analyse spins forever on PDF uploads",
                   "description": "### What happened\nPressing Analyse on a PDF never finishes; it just spins."})
    assert tidy["title"] == "Analyse spins forever on PDF uploads"
    assert accept({"title": "", "description": "x"}) is None
    assert accept({"title": "Bug", "description": "word " * 200}) is None  # far longer: things were added


def test_paraphrases_must_be_in_both_texts():
    source = "The glucose stores chemical energy that the plant later uses to grow."
    draft = "My intro. Sugar holds energy the plant uses later for growth. My end."
    task, _ = plagiarism_task({"Biology book": source}, draft)
    assert 'SOURCE "Biology book"' in task and "THE DRAFT" in task
    found = accept_plagiarism({"Biology book": source}, draft)({"paraphrases": [
        {"draft": "Sugar holds energy the plant uses later for growth", "source": "Biology book",
         "source_quote": "The glucose stores chemical energy", "why": "Same idea reworded."},
        {"draft": "Sugar holds energy", "source": "Biology book", "source_quote": "glucose", "why": "overlap"},
        {"draft": "My end", "source": "Biology book", "source_quote": "not in the source", "why": "made up"},
    ]})
    assert len(found) == 1
    assert draft[found[0].start:found[0].end] == "Sugar holds energy the plant uses later for growth"
    assert found[0].source_quote == "The glucose stores chemical energy"


def test_citation_fields_come_only_from_the_text():
    text = "lecun bengio hinton 2015 deep learning nature"
    assert "deep learning" in citation_task(text)[0]
    fields = accept_citation(text)({"kind": "article", "title": "Deep learning", "authors": ["LeCun, Yann", "Smith, J"],
                                    "year": "2015", "container": "Nature", "volume": "521", "doi": "10.1038/x"})
    assert fields["title"] == "Deep learning" and fields["year"] == "2015" and fields["kind"] == "article"
    assert fields["authors"] == ["LeCun, Yann"] and fields["container"] == "Nature"
    assert fields["volume"] == "" and fields["doi"] == ""  # not in what was typed
    made_up = accept_citation(text)({"title": "Deep learning", "year": "1999", "kind": "poem"})
    assert made_up["year"] == "" and made_up["kind"] == "article"
    assert accept_citation(text)({"title": "A title that isn't there"}) is None
    austen = "Austen, J. Pride and Prejudice. London: T. Egerton, 1813."
    assert accept_citation(austen)({"title": "Pride and Prejudice", "authors": ["Jane Austen"]})["authors"] == \
        ["Austen, Jane"]
