from pathlib import Path

from streamlit.testing.v1 import AppTest

import citations

APP = str(Path(__file__).parent.parent / "app.py")
CFG = {"client_id": "cid", "client_secret": "cs", "redirect_uri": "http://localhost:8501", "allowed_users": ["tester"]}


def signed_in_app(page: str = "checker") -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.secrets["github"] = CFG
    at.session_state["user"] = "tester"
    at.session_state["page"] = page
    return at


def run_with(text: str) -> AppTest:
    at = signed_in_app().run()
    at.text_area(key="checker_text").input(text)
    at.button(key="analyse").click().run()
    return at


def markdown_html(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown)


# ---- writing checker --------------------------------------------------------

def test_app_shows_metrics_and_suggestions():
    at = run_with("The report was written by the team. Due to the fact that it rained, we stayed.")
    assert not at.exception
    assert len(at.metric) == 4
    page = markdown_html(at)
    assert '<div class="uf-card uf-card-grammar"><b>Passive voice</b>' in page
    assert "The report was written by the team.</div>" in page
    assert 'uf-card-style"><b>Wordy phrase</b> → “due to the fact that” ×1: replace with <b>because</b>' in page


def test_issue_cards_escape_user_text():
    at = run_with("The <b>report</b> was written by the team.")
    page = markdown_html(at)
    assert "The &lt;b&gt;report&lt;/b&gt; was written by the team." in page


def test_sample_button_fills_text_and_shows_score():
    at = signed_in_app().run()
    at.button(key="sample_checker").click().run()
    assert at.text_area(key="checker_text").value.startswith("It is important to note")
    at.button(key="analyse").click().run()
    assert not at.exception
    page = markdown_html(at)
    assert 'class="uf-score"' in page and "Writing score" in page
    assert any(m.label == "Grade level" for m in at.metric)
    improved = at.code[0].value
    assert improved.startswith("The results of the survey were analysed")
    assert "Because many students struggled" in improved


def test_app_shows_new_checks_times_and_downloads():
    at = run_with("We don't think outside the box. We analysed it, then organized it.")
    assert not at.exception
    page = markdown_html(at)
    assert "<b>Cliché</b>" in page and 'class="uf-cliche"' in page
    assert "<b>Contractions</b>" in page and "do not" in page
    assert "<b>Mixed UK/US spelling</b>" in page and 'class="uf-spelling"' in page
    assert "Reading: under 1 min | Speaking: under 1 min" in page
    words = next(m for m in at.metric if m.label == "Words")
    assert "read" in words.proto.delta
    labels = [b.proto.label for b in at.get("download_button")]
    assert {"PDF (.pdf)", "Word (.docx)", "Markdown (.md)"} <= set(labels)


def test_app_shows_spelling_tone_and_starts():
    at = run_with("You recieve it. You are gonna win. You know it.")
    assert not at.exception
    page = markdown_html(at)
    assert "<b>Spelling</b>" in page and "<i>recieve</i> → <b>receive</b>" in page
    assert 'class="uf-typo"' in page and 'class="uf-informal"' in page and "uf-starts" in page
    assert "<b>Informal words</b>" in page and "<b>Talking to the reader</b>" in page
    assert "<b>Repeated sentence starts</b>" in page
    assert any("Still to fix yourself: 1 spelling mistake(s)" in c.value for c in at.caption)


def test_second_draft_shows_score_change():
    at = run_with("We don't think outside the box. Due to the fact that it rained, we stayed in order to rest.")
    assert 'class="uf-drafts"' not in markdown_html(at)  # nothing to compare the first draft with
    at.text_area(key="checker_text").input("We stayed because it rained.")
    at.button(key="analyse").click().run()
    page = markdown_html(at)
    assert "Since your last draft:" in page and "since last draft" in page
    assert "Fixed: 2 wordy phrases, 1 cliché, 1 contraction" in page
    # analysing the same text again still compares with the earlier draft
    at.button(key="analyse").click().run()
    assert "Fixed: 2 wordy phrases" in markdown_html(at)


def test_clear_all_forgets_previous_draft():
    at = run_with("We don't think outside the box.")
    at.button(key="clear_checker").click().run()
    at.text_area(key="checker_text").input("Cats chase mice.")
    at.button(key="analyse").click().run()
    assert 'class="uf-drafts"' not in markdown_html(at)


def test_word_limit():
    at = signed_in_app().run()
    at.number_input(key="word_limit").set_value(10)
    at.text_area(key="checker_text").input("one two three four five six seven eight nine ten eleven twelve").run()
    assert "2 words over the 10-word limit." in at.warning[0].value
    at.text_area(key="checker_text").input("one two three").run()
    assert not at.warning
    assert "Aim for at least 9 (6 more)" in at.get("progress")[0].proto.text
    at.number_input(key="word_limit").set_value(0).run()
    assert not at.get("progress")


def test_sentence_chart_and_variety_card():
    at = run_with(" ".join(["The cat sat on the warm mat today."] * 6))
    assert not at.exception
    assert "<b>Sentence variety</b>" in markdown_html(at)
    assert len(at.get("vega_lite_chart")) == 1


def test_app_highlights_issues():
    at = run_with("Due to the fact that it rained, we really stayed.")
    page = markdown_html(at)
    assert 'class="uf-wordy"' in page and 'class="uf-adverb"' in page


def test_highlight_escapes_html():
    at = run_with("<script>alert(1)</script> is really bad.")
    assert not at.exception
    page = markdown_html(at)
    assert "&lt;script&gt;" in page and "<script>alert" not in page


def test_app_clean_text_shows_success():
    at = run_with("Cats chase mice.")
    assert not at.exception
    assert at.success


def test_app_has_upload_tab():
    at = signed_in_app().run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Paste text", "Upload document"]


def test_app_empty_input_does_nothing():
    at = signed_in_app().run()
    at.button(key="analyse").click().run()
    assert not at.exception
    assert len(at.metric) == 0


def test_clear_all_empties_text():
    at = signed_in_app().run()
    at.text_area(key="checker_text").input("Some text.").run()
    at.button(key="clear_checker").click().run()
    assert at.text_area(key="checker_text").value == ""


# ---- navigation ---------------------------------------------------------------

def test_top_navigation_switches_page():
    at = signed_in_app().run()
    assert at.button(key="nav_checker").proto.type == "primary"
    at.button(key="nav_similarity").click().run()
    assert not at.exception
    assert at.session_state["page"] == "similarity"
    assert at.button(key="nav_similarity").proto.type == "primary"
    assert at.button(key="nav_checker").proto.type == "secondary"


def test_text_survives_switching_pages():
    at = signed_in_app().run()
    at.text_area(key="checker_text").input("Keep me.").run()
    at.button(key="nav_citations").click().run()
    at.button(key="nav_checker").click().run()
    assert at.text_area(key="checker_text").value == "Keep me."


def test_every_page_renders():
    for page in ("checker", "plagiarism", "citations", "similarity", "feedback", "about"):
        at = signed_in_app(page).run()
        assert not at.exception, page


def test_logout_returns_to_sign_in():
    at = signed_in_app().run()
    at.button(key="logout").click().run()
    assert "user" not in at.session_state


# ---- pages ----------------------------------------------------------------------

def test_similarity_page_compares():
    shared = "the quick brown fox jumps over the lazy dog near the river bank"
    at = signed_in_app("similarity").run()
    at.text_area(key="doc_a").input(f"Intro words here. {shared}. More of A.")
    at.text_area(key="doc_b").input(f"Different start. {shared}. Ending of B.")
    at.button(key="compare").click().run()
    assert not at.exception
    assert len(at.metric) == 4
    assert 'class="uf-match"' in markdown_html(at)


def test_similarity_page_needs_both_documents():
    at = signed_in_app("similarity").run()
    at.text_area(key="doc_a").input("Only one document.")
    at.button(key="compare").click().run()
    assert at.warning


def test_plagiarism_page_flags_uncited_match():
    source = "the committee reviewed every budget line before approving the final plan for next year"
    at = signed_in_app("plagiarism").run()
    at.text_area(key="plag_draft").input(f"My intro. {source}. My ending.")
    at.text_area(key="plag_source_text").input(source)
    at.button(key="plag_check").click().run()
    assert not at.exception
    assert len(at.metric) == 3
    assert 'uf-card-plagiarism' in markdown_html(at)
    assert 'class="uf-uncited"' in markdown_html(at)


def test_quick_plagiarism_check_with_example():
    at = signed_in_app("plagiarism").run()
    at.selectbox(key="plag_example").select("High similarity").run()
    assert at.text_area(key="plag_source").value
    at.button(key="plag_quick").click().run()
    assert not at.exception
    assert any("Matched words" == m.label for m in at.metric)
    assert 'class="uf-match"' in markdown_html(at)
    assert "Identical phrase sequences" in markdown_html(at)
    assert '" (Source)' in at.code[0].value


def test_quick_plagiarism_check_needs_both_texts():
    at = signed_in_app("plagiarism").run()
    at.text_area(key="plag_source").input("Only a source.")
    at.button(key="plag_quick").click().run()
    assert at.warning


def test_plagiarism_page_needs_a_source():
    at = signed_in_app("plagiarism").run()
    at.text_area(key="plag_draft").input("Just a draft.")
    at.button(key="plag_check").click().run()
    assert any("source" in w.value for w in at.warning)


def test_citations_page_inserts():
    at = signed_in_app("citations")
    at.session_state["refs"] = [citations.Reference(key="smith2020", kind="article", title="A study", authors=["Smith, Jane"], year="2020")]
    at.run()
    at.selectbox(key="cite_style").select("APA")
    at.text_area(key="cite_text").input("Cats purr [@smith2020]. Dogs bark [@nobody].")
    at.button(key="insert_citations").click().run()
    assert not at.exception
    outputs = [t.value for t in at.text_area]
    assert "Cats purr (Smith, 2020). Dogs bark [@nobody]." in outputs
    assert any("nobody" in w.value for w in at.warning)


def test_feedback_page_builds_issue_link():
    at = signed_in_app("feedback").run()
    at.text_input[0].input("Add Chicago style")
    next(b for b in at.button if b.label.startswith("Submit Report")).click().run()
    assert not at.exception
    assert at.success
