import hashlib
import html
import math

import streamlit as st

from analysis import (
    ENDING_ADVICE, LONG_SENTENCE_WORDS, READ_WPM, SPEAK_WPM, analyze, duration, expand_contraction, grade_label,
    split_sentences,
)
from documents import SUPPORTED, DocumentError, clean_pasted, extract_text
from fixes import apply_fixes
from highlight import find_spans, legend_html, render_html
from lessons import LESSONS
from modes import DEFAULT_MODE, MODES, apply_mode, hidden_spans, ignored
from nlp_checks import REPEAT_MIN, check
from report import build_docx, build_markdown, build_pdf
from score import compare_drafts, describe_counts, issue_counts, score_label, writing_score
from structure import effort_summary, outline, sentence_effort, word_budget
from ui.listen import render_listen
from ui.theme import card_html, counter, feed, final_output

MAX_CHARS = 200_000
WORD_LIMIT_SLACK = 0.1  # within 10% under the limit counts as on target
DRAFT_KEYS = ("draft_last", "draft_prev")

# A demo paragraph with one of each issue, so the checker can be shown in one click.
SAMPLE_TEXT = (
    "It is important to note that the results of the survey were analysed by the research team. "
    "Due to the fact that a large number of students really struggled with the new timetable, the school "
    "decided that it would be basically necessary to make some changes to the way that classes were "
    "organised across the whole of the second term. In order to fix this, a meeting was held. "
    "The meeting was very useful and the meeting helped the meeting organisers get feedback."
)


def load_sample() -> None:
    st.session_state["checker_text"] = SAMPLE_TEXT


def clear_checker() -> None:
    """Empty the text and forget the previous draft, since the next text is probably a new piece of writing."""
    st.session_state["checker_text"] = ""
    for key in DRAFT_KEYS:
        st.session_state.pop(key, None)


def fix_pasted() -> None:
    text, fixed = clean_pasted(st.session_state.get("checker_text", ""))
    st.session_state["checker_text"] = text
    st.session_state["fix_msg"] = ("Fixed: " + "; ".join(fixed) + ".") if fixed else "Nothing to fix: the text looks clean."


def mode() -> str:
    return st.session_state.get("writing_mode") or DEFAULT_MODE


def issue(kind: str, title: str, advice: str, quote: str = "") -> str:
    """An issue card with its lesson ("Why?") when there is one."""
    return card_html(kind, title, advice, quote, LESSONS.get(title))


def score_ring_html(score: int, change: int | None = None) -> str:
    color = "#4ade80" if score >= 70 else "#f59e0b" if score >= 50 else "#F05252"
    since = ""
    if change:
        arrow = "uf-up" if change > 0 else "uf-down"
        since = f'<div class="uf-score-change {arrow}">{change:+d} since last draft</div>'
    return (
        f'<div class="uf-score"><div class="uf-ring" style="background:conic-gradient({color} {score * 3.6}deg,'
        f'rgba(255,255,255,.08) 0)"><div class="uf-ring-inner"><b>{score}</b><small>/ 100</small></div></div>'
        f'<div><div class="uf-score-title">Writing score</div>'
        f'<div class="uf-score-label" style="color:{color}">{score_label(score)}</div>{since}</div></div>'
    )


def word_limit_status(words: int, limit: int) -> tuple[str, str]:
    """("over" | "under" | "ok", message) for a text of `words` against a word limit."""
    if words > limit:
        return "over", f"{words - limit:,} words over the {limit:,}-word limit."
    floor = math.ceil(limit * (1 - WORD_LIMIT_SLACK))
    if words < floor:
        return "under", f"{words:,} / {limit:,} words. Aim for at least {floor:,} ({floor - words:,} more)."
    return "ok", f"{words:,} / {limit:,} words. On target."


def show_word_limit(words: int) -> None:
    limit = st.session_state.get("word_limit") or 0
    if not limit:
        return
    status, message = word_limit_status(words, limit)
    if status == "over":
        st.warning(message, icon=":material/warning:")
    else:
        st.progress(min(words / limit, 1.0), text=message)


def track_draft(text: str, score: int, counts: dict[str, int]) -> dict | None:
    """Remember this analysis and return the previous, different draft (or None).
    Re-analysing the same text keeps comparing against the same earlier draft."""
    digest = hashlib.sha256(text.encode()).hexdigest()
    last = st.session_state.get("draft_last")
    if last and last["digest"] != digest:
        st.session_state["draft_prev"] = last
    st.session_state["draft_last"] = {"digest": digest, "score": score, "counts": counts}
    return st.session_state.get("draft_prev")


def draft_change_html(prev: dict, score: int, counts: dict[str, int]) -> str:
    fixed, new = compare_drafts(prev["counts"], counts)
    parts = [f"Since your last draft: <b>{prev['score']} → {score}</b> ({score - prev['score']:+d})"]
    if fixed:
        parts.append(f'<span class="uf-up">Fixed: {describe_counts(fixed)}</span>')
    if new:
        parts.append(f'<span class="uf-down">New: {describe_counts(new)}</span>')
    if not fixed and not new:
        parts.append("Same issues as before")
    return f'<div class="uf-drafts">{" · ".join(parts)}</div>'


def render_sentence_chart(text: str, lengths: list[int]) -> None:
    """Words per sentence as bars, with a dashed line where sentences count as long."""
    import altair as alt
    import pandas as pd

    sentences = split_sentences(text)
    data = pd.DataFrame({
        "Sentence": range(1, len(lengths) + 1),
        "Words": lengths,
        "Text": [s if len(s) <= 90 else s[:87] + "..." for s in sentences],
    })
    bars = alt.Chart(data).mark_bar(color="#06B6D4", cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("Sentence:O", axis=alt.Axis(labelAngle=0, labelOverlap=True, grid=False)),
        y=alt.Y("Words:Q", axis=alt.Axis(tickCount=5)),
        tooltip=["Sentence", "Words", "Text"],
    )
    line = alt.Chart(pd.DataFrame({"Words": [LONG_SENTENCE_WORDS]})).mark_rule(
        color="#94A3B8", strokeDash=[4, 4]).encode(y="Words:Q")
    label = line.mark_text(align="left", dx=4, dy=-7, color="#94A3B8", text=f"long ({LONG_SENTENCE_WORDS}+)").encode(
        x=alt.value(0))
    st.altair_chart((bars + line + label).properties(height=220), width="stretch")


def render_highlighted(text: str, report, box) -> None:
    hidden = hidden_spans(mode())
    spans = [s for s in find_spans(text, report) if s[2] not in hidden]
    kinds = ("typo", "opening", "wordy", "cliche", "informal", "adverb", "contraction", "spelling", "starts",
             "passive", "long")
    present = [c for c in kinds if any(s[2] == c for s in spans)]
    with box:
        if present:
            st.markdown(legend_html(present), unsafe_allow_html=True)
        st.markdown(render_html(text, spans), unsafe_allow_html=True)


def word_list(counts: list[tuple[str, int]]) -> str:
    return ", ".join(f"<i>{html.escape(w)}</i> ×{n}" for w, n in counts)


def render_issues(report, nlp) -> None:
    """Each finding as a card saying what to do: gold for grammar, blue for style."""
    found_nlp = nlp.passive or nlp.repeated or nlp.weak_verbs or nlp.adverbs
    found = (report.long_sentences or report.wordy or report.cliches or report.contractions or report.uk_spelling
             or report.monotonous or report.misspellings or report.informal or report.second_person
             or report.repeated_starts or report.weak_openings or report.ending_issues)
    if not found and not found_nlp:
        st.success("No issues found. Nice and clear!")
    if not nlp.available:
        st.warning("Grammar checks unavailable: run `python -m spacy download en_core_web_sm`.")

    cards = []
    if report.misspellings:
        fixes = ", ".join(f"<i>{html.escape(w)}</i> → <b>{html.escape(fix)}</b>" + (f" ×{n}" if n > 1 else "")
                          for w, fix, n in report.misspellings)
        cards.append(issue("grammar", "Spelling", f"probable mistakes: {fixes}"))
    for phrase in report.weak_openings:
        cards.append(issue("style", "Weak opening", f"“{html.escape(phrase)}” tells the reader little. Open with your "
                                                    "own point about the topic"))
    cards += [issue("grammar", "Passive voice", "say who does the action", s) for s in nlp.passive]
    if report.informal:
        swaps = ", ".join(f"<i>{html.escape(p)}</i> → {html.escape(s)}" + (f" ×{n}" if n > 1 else "")
                          for p, s, n in report.informal)
        cards.append(issue("style", "Informal words", f"for essays and reports: {swaps}"))
    if report.second_person:
        cards.append(issue("style", "Talking to the reader",
                           f"“you” / “your” ×{report.second_person}. Formal writing usually avoids addressing "
                           "the reader: try “people”, “students”, “one” or the passive"))
    for word, _, length in report.repeated_starts:
        cards.append(issue("style", "Repeated sentence starts",
                           f"{length} sentences in a row begin with “{html.escape(word.capitalize())}”. "
                           "Vary how they open"))
    for phrase, suggestion, hits in report.wordy:
        cards.append(issue("style", "Wordy phrase", f"“{phrase}” ×{hits}: replace with <b>{suggestion}</b>"))
    for phrase, hits in report.cliches:
        cards.append(issue("style", "Cliché", f"“{phrase}” ×{hits}: say it in your own words"))
    if report.uk_spelling:
        cards.append(issue("grammar", "Mixed UK/US spelling",
                           f"pick one. UK: {word_list(report.uk_spelling)}. US: {word_list(report.us_spelling)}. "
                           f"Fewest changes: fix {word_list(report.minority_spelling)}"))
    if report.monotonous:
        avg = round(sum(report.sentence_lengths) / len(report.sentence_lengths))
        cards.append(issue("style", "Sentence variety",
                           f"most sentences are about {avg} words long. Mix in some short ones and some longer "
                           "ones so the writing doesn't sound flat (see the chart below)"))
    for s in report.long_sentences:
        cards.append(issue("style", "Long sentence", f"{len(s.split())} words (over {LONG_SENTENCE_WORDS}): split it in two", s))
    if nlp.adverbs:
        cards.append(issue("style", "Filler adverbs", f"usually cut them: {word_list(nlp.adverbs)}"))
    if nlp.weak_verbs:
        cards.append(issue("style", "Weak verbs", f"a more specific verb is often clearer: {word_list(nlp.weak_verbs)}"))
    if nlp.repeated:
        cards.append(issue("style", "Repeated words", f"used {REPEAT_MIN}+ times, consider varying: {word_list(nlp.repeated)}"))
    if report.contractions:
        expanded = ", ".join(f"<i>{html.escape(w)}</i> → {html.escape(expand_contraction(w))}" for w, _ in report.contractions)
        cards.append(issue("style", "Contractions", f"fine in casual writing; in essays write them out: {expanded}"))
    cards += [issue("style", "Conclusion", ENDING_ADVICE[k]) for k in report.ending_issues]
    feed(cards)


def render_outline(text: str) -> None:
    points = outline(text)
    if len(points) < 2:
        st.info("Your text is one paragraph. Leave a blank line between paragraphs to see an outline of them.",
                icon=":material/info:")
        return
    st.caption("One line per paragraph: its first sentence (usually the main point) and its key words. Read down "
               "the list: does each paragraph make one clear point, in an order that builds?")
    rows = []
    for p in points:
        notes = "".join(f'<div class="uf-op-note">⚠ {html.escape(n)}</div>' for n in p.notes)
        rows.append(
            f'<div class="uf-op"><div class="uf-op-num">{p.number}</div><div><div>{html.escape(p.main_point)}</div>'
            f'<div class="uf-op-meta">{p.words} words · {p.sentences} sentence{"s" if p.sentences != 1 else ""}'
            f' · key words: {html.escape(", ".join(p.key_words))}</div>{notes}</div></div>'
        )
    st.markdown(f'<div class="uf-outline">{"".join(rows)}</div>', unsafe_allow_html=True)


def budget_html(intro: int, body: int, conclusion: int) -> str:
    total = intro + body + conclusion
    parts = (("Intro", intro, "uf-b-intro"), ("Body", body, "uf-b-body"), ("Conclusion", conclusion, "uf-b-end"))
    bar = "".join(
        f'<div class="{cls}" style="flex:{max(n, 1)}" title="{name}: {n} words ({n / total:.0%})">'
        f'{f"{name} {n / total:.0%}" if n / total >= 0.12 else ""}</div>'
        for name, n, cls in parts
    )
    key = "".join(f'<span><i class="{cls}"></i>{name}: {n:,} words ({n / total:.0%})</span>' for name, n, cls in parts)
    return f'<div class="uf-budget" role="img" aria-label="Word budget">{bar}</div><div class="uf-budget-key">{key}</div>'


def render_budget(text: str) -> None:
    budget = word_budget(text)
    if budget is None:
        st.info("Needs at least 3 paragraphs (an introduction, a body and a conclusion), separated by blank lines.",
                icon=":material/info:")
        return
    st.caption("How your words are split between the first paragraph, the middle ones and the last. Most essays "
               "spend about 10% on each end and the rest on the main points.")
    st.markdown(budget_html(budget.intro, budget.body, budget.conclusion), unsafe_allow_html=True)
    for advice in budget.advice:
        st.warning(advice, icon=":material/balance:")
    if not budget.advice:
        st.success("Well balanced: the main points get most of the space.", icon=":material/check_circle:")


def render_effort(text: str, nlp) -> None:
    efforts = sentence_effort(text, nlp.passive)
    if not efforts:
        return
    counts = effort_summary(efforts)
    st.caption("Each sentence coloured by how much work it asks of the reader: its length, its long words and "
               "the passive voice. Darker = harder. A few hard sentences are fine; long runs of them tire readers.")
    spans = [(e.start, e.end, f"effort-{e.level}") for e in efforts]
    st.markdown(legend_html(["effort-easy", "effort-medium", "effort-hard"]), unsafe_allow_html=True)
    st.markdown(render_html(text, spans), unsafe_allow_html=True)
    st.caption(f"{counts['easy']} easy, {counts['medium']} medium and {counts['hard']} hard sentence(s).")


def render_deeper_look(text: str, nlp) -> None:
    st.markdown("#### :material/insights: Deeper look")
    t_outline, t_budget, t_effort, t_listen = st.tabs(["Reverse outline", "Word budget", "Reader effort", "Listen"])
    with t_outline:
        render_outline(text)
    with t_budget:
        render_budget(text)
    with t_effort:
        render_effort(text, nlp)
    with t_listen:
        st.caption("Your browser reads the text aloud and highlights each sentence. Hearing your writing is one of "
                   "the best ways to catch clumsy sentences.")
        render_listen(split_sentences(text))


def render_improved(text: str, report, nlp) -> None:
    fixed = apply_fixes(text, expand_contractions="contraction" not in ignored(mode()))
    if fixed.changes:
        done = ", ".join(f"“{p}” → {r or 'removed'}" + (f" ×{n}" if n > 1 else "") for p, r, n in fixed.changes)
        note = f"Easy fixes applied: {done}."
    else:
        note = "No automatic fixes were needed."
    todo = [f"{len(report.misspellings)} spelling mistake(s)" if report.misspellings else "",
            f"{len(nlp.passive)} passive sentence(s)" if nlp.passive else "",
            f"{len(report.long_sentences)} long sentence(s)" if report.long_sentences else ""]
    if todo := [t for t in todo if t]:
        note += f" Still to fix yourself: {', '.join(todo)} (see the cards above)."
    final_output("checker", "Improved Text", fixed.text, note, "improved-text.txt")


def render_report(text: str, source: str, highlight_box=None) -> None:
    if len(text) > MAX_CHARS:
        st.warning(f"Text is long; analysing the first {MAX_CHARS:,} characters.")
        text = text[:MAX_CHARS]

    report, nlp = apply_mode(analyze(text), check(text), mode())
    score, counts = writing_score(report, nlp), issue_counts(report, nlp)
    prev = track_draft(text, score, counts)

    ring, c1, c2, c3, c4 = st.columns([2, 1, 1, 1, 1], vertical_alignment="center")
    ring.markdown(score_ring_html(score, score - prev["score"] if prev else None), unsafe_allow_html=True)
    c1.metric("Words", report.words, delta=f"{duration(report.words, READ_WPM)} read", delta_color="off",
              help=f"Reading time at {READ_WPM} words a minute. Spoken aloud (e.g. a presentation) at "
                   f"{SPEAK_WPM} words a minute: {duration(report.words, SPEAK_WPM)}.")
    c2.metric("Sentences", report.sentences, help=f"Average {report.avg_sentence_len:.1f} words per sentence.")
    c3.metric("Reading ease", f"{report.reading_ease:.0f}", help="Flesch score: 60-70 is plain English; higher is easier.")
    c4.metric("Grade level", f"{report.grade_level:.0f}", delta=grade_label(report.grade_level), delta_color="off",
              help="Flesch-Kincaid: the school year (US grades) a reader needs to follow the text easily.")
    if prev:
        st.markdown(draft_change_html(prev, score, counts), unsafe_allow_html=True)

    box = highlight_box if highlight_box is not None else st.container()
    render_highlighted(text, report, box)
    with box:
        render_issues(report, nlp)

    if len(report.sentence_lengths) > 1:
        st.markdown("#### :material/bar_chart: Sentence lengths")
        st.caption(f"Words in each sentence, in order (average {report.avg_sentence_len:.0f}). Good writing mixes "
                   "short and long sentences. Hover a bar to see the sentence.")
        render_sentence_chart(text, report.sentence_lengths)

    render_deeper_look(text, nlp)
    render_improved(text, report, nlp)

    st.markdown("#### :material/download: Download report")
    d_pdf, d_docx, d_md = st.columns(3)
    d_pdf.download_button("PDF (.pdf)", build_pdf(report, nlp, source), "writelens-report.pdf", "application/pdf",
                          key="report_pdf", icon=":material/picture_as_pdf:", on_click="ignore", width="stretch")
    d_docx.download_button("Word (.docx)", build_docx(report, nlp, source), "writelens-report.docx",
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                           key="report_docx", icon=":material/description:", on_click="ignore", width="stretch")
    d_md.download_button("Markdown (.md)", build_markdown(report, nlp, source), "writelens-report.md", "text/markdown",
                         key="report_md", icon=":material/article:", on_click="ignore", width="stretch")


def render() -> None:
    st.markdown("### :material/edit_note: Writing Checker")
    st.write("Paste text or upload a document. Problems are highlighted in place; you decide what to change.")

    tab_paste, tab_upload = st.tabs(["Paste text", "Upload document"])

    with tab_paste:
        st.markdown("#### Your Text")
        text = st.text_area(
            "Your text", key="checker_text", height=320,
            placeholder="Paste a paragraph or more...", label_visibility="collapsed",
        )
        counter(text)
        mode_col, limit_col, _ = st.columns([1, 1, 2])
        mode_col.selectbox("Writing type", list(MODES), key="writing_mode",
                           help="Turns off checks that don't suit the kind of text. "
                                + " ".join(f"**{name}**: {desc}" for name, (desc, _) in MODES.items()))
        limit_col.number_input("Word limit (optional)", min_value=0, max_value=100_000, step=100, key="word_limit",
                               help="Your assignment's word limit. Leave at 0 for none.")
        st.caption(MODES[mode()][0])
        show_word_limit(len(text.split()))
        b_analyse, b_fix, b_clear, b_sample = st.columns([2, 1, 1, 1])
        analyse = b_analyse.button("Analyse Text", key="analyse", type="primary", icon=":material/auto_fix_high:", width="stretch")
        b_fix.button("Fix pasted text", key="fix_pasted", icon=":material/cleaning_services:", width="stretch",
                     on_click=fix_pasted, help="Joins lines broken by copying from a PDF, rejoins split words, and "
                                               "removes page numbers, double spaces and invisible characters.")
        b_clear.button("Clear All", key="clear_checker", icon=":material/delete:", width="stretch",
                       on_click=clear_checker)
        b_sample.button("Try a sample", key="sample_checker", icon=":material/lightbulb:", width="stretch",
                        on_click=load_sample)
        if msg := st.session_state.pop("fix_msg", None):
            st.success(msg, icon=":material/cleaning_services:")

        st.markdown("#### Highlighted Issues")
        if analyse and text.strip():
            render_report(text, "Pasted text")
        else:
            st.markdown('<div class="uf-placeholder">Analyse your text to see highlights and suggestions here.</div>',
                        unsafe_allow_html=True)

    with tab_upload:
        uploaded = st.file_uploader(f"Upload a document ({', '.join('.' + e for e in SUPPORTED)})", type=list(SUPPORTED))
        if uploaded is not None:
            try:
                doc_text = extract_text(uploaded.name, uploaded.getvalue())
            except DocumentError as exc:
                st.error(str(exc))
            else:
                st.caption(f"Extracted {len(doc_text.split()):,} words from **{uploaded.name}**.")
                show_word_limit(len(doc_text.split()))
                if st.button("Analyse Document", key="analyse_doc", type="primary", icon=":material/auto_fix_high:"):
                    st.markdown("#### Highlighted Issues")
                    render_report(doc_text, uploaded.name)
