import hashlib
import html
import math

import streamlit as st

from analysis import (
    LONG_SENTENCE_WORDS, READ_WPM, SPEAK_WPM, analyze, duration, expand_contraction, grade_label, split_sentences,
)
from documents import SUPPORTED, DocumentError, extract_text
from fixes import apply_fixes
from highlight import find_spans, legend_html, render_html
from nlp_checks import REPEAT_MIN, check
from report import build_docx, build_markdown, build_pdf
from score import compare_drafts, describe_counts, issue_counts, score_label, writing_score
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
    st.altair_chart((bars + line + label).properties(height=220), use_container_width=True)


def render_highlighted(text: str, box) -> None:
    spans = find_spans(text)
    kinds = ("wordy", "cliche", "adverb", "contraction", "spelling", "passive", "long")
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
             or report.monotonous)
    if not found and not found_nlp:
        st.success("No issues found. Nice and clear!")
    if not nlp.available:
        st.warning("Grammar checks unavailable: run `python -m spacy download en_core_web_sm`.")

    cards = [card_html("grammar", "Passive voice", "say who does the action", s) for s in nlp.passive]
    for phrase, suggestion, hits in report.wordy:
        cards.append(card_html("style", "Wordy phrase", f"“{phrase}” ×{hits}: replace with <b>{suggestion}</b>"))
    for phrase, hits in report.cliches:
        cards.append(card_html("style", "Cliché", f"“{phrase}” ×{hits}: say it in your own words"))
    if report.uk_spelling:
        cards.append(card_html("grammar", "Mixed UK/US spelling",
                               f"pick one. UK: {word_list(report.uk_spelling)}. US: {word_list(report.us_spelling)}. "
                               f"Fewest changes: fix {word_list(report.minority_spelling)}"))
    if report.monotonous:
        avg = round(sum(report.sentence_lengths) / len(report.sentence_lengths))
        cards.append(card_html("style", "Sentence variety",
                               f"most sentences are about {avg} words long. Mix in some short ones and some longer "
                               "ones so the writing doesn't sound flat (see the chart below)"))
    for s in report.long_sentences:
        cards.append(card_html("style", "Long sentence", f"{len(s.split())} words (over {LONG_SENTENCE_WORDS}): split it in two", s))
    if nlp.adverbs:
        cards.append(card_html("style", "Filler adverbs", f"usually cut them: {word_list(nlp.adverbs)}"))
    if nlp.weak_verbs:
        cards.append(card_html("style", "Weak verbs", f"a more specific verb is often clearer: {word_list(nlp.weak_verbs)}"))
    if nlp.repeated:
        cards.append(card_html("style", "Repeated words", f"used {REPEAT_MIN}+ times, consider varying: {word_list(nlp.repeated)}"))
    if report.contractions:
        expanded = ", ".join(f"<i>{html.escape(w)}</i> → {html.escape(expand_contraction(w))}" for w, _ in report.contractions)
        cards.append(card_html("style", "Contractions", f"fine in casual writing; in essays write them out: {expanded}"))
    feed(cards)


def render_improved(text: str, report, nlp) -> None:
    fixed = apply_fixes(text)
    if fixed.changes:
        done = ", ".join(f"“{p}” → {r or 'removed'}" + (f" ×{n}" if n > 1 else "") for p, r, n in fixed.changes)
        note = f"Easy fixes applied: {done}."
    else:
        note = "No automatic fixes were needed."
    todo = [f"{len(nlp.passive)} passive sentence(s)" if nlp.passive else "",
            f"{len(report.long_sentences)} long sentence(s)" if report.long_sentences else ""]
    if todo := [t for t in todo if t]:
        note += f" Still to fix yourself: {' and '.join(todo)} (see the cards above)."
    final_output("checker", "Improved Text", fixed.text, note, "improved-text.txt")


def render_report(text: str, source: str, highlight_box=None) -> None:
    if len(text) > MAX_CHARS:
        st.warning(f"Text is long; analysing the first {MAX_CHARS:,} characters.")
        text = text[:MAX_CHARS]

    report = analyze(text)
    nlp = check(text)
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
    render_highlighted(text, box)
    with box:
        render_issues(report, nlp)

    if len(report.sentence_lengths) > 1:
        st.markdown("#### :material/bar_chart: Sentence lengths")
        st.caption(f"Words in each sentence, in order (average {report.avg_sentence_len:.0f}). Good writing mixes "
                   "short and long sentences. Hover a bar to see the sentence.")
        render_sentence_chart(text, report.sentence_lengths)

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
        limit_col, _ = st.columns([1, 3])
        limit_col.number_input("Word limit (optional)", min_value=0, max_value=100_000, step=100, key="word_limit",
                               help="Your assignment's word limit. Leave at 0 for none.")
        show_word_limit(len(text.split()))
        b_analyse, b_clear, b_sample = st.columns([2, 1, 1])
        analyse = b_analyse.button("Analyse Text", key="analyse", type="primary", icon=":material/auto_fix_high:", width="stretch")
        b_clear.button("Clear All", key="clear_checker", icon=":material/delete:", width="stretch",
                       on_click=clear_checker)
        b_sample.button("Try a sample", key="sample_checker", icon=":material/lightbulb:", width="stretch",
                        on_click=load_sample)

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
