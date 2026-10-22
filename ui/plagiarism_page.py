import streamlit as st

from documents import SUPPORTED, DocumentError, extract_text
from highlight import legend_html, render_html
from plagiarism import MAX_SOURCES, check, quick_check, quote_and_cite
from similarity import MATCH_WORDS
from ui.theme import card, clear_keys, counter, final_output

FILE_TYPES = ", ".join("." + e for e in SUPPORTED)

EXAMPLE_SOURCE = (
    "Photosynthesis is the process by which green plants and some other organisms use sunlight to turn water "
    "and carbon dioxide into glucose and oxygen. The glucose stores chemical energy that the plant later uses "
    "to grow, while the oxygen is released into the air."
)
# example name -> submission text
EXAMPLES = {
    "High similarity": (
        "Photosynthesis is the process by which green plants and some other organisms use sunlight to turn "
        "water and carbon dioxide into sugar and oxygen. The glucose stores chemical energy that the plant "
        "later uses to grow."
    ),
    "Some overlap": (
        "Plants make their own food. Photosynthesis is the process by which green plants and some other "
        "organisms use sunlight, and the sugar they make powers their growth while oxygen escapes into the air."
    ),
    "Original": (
        "Leaves look green because chlorophyll reflects green light. In autumn the chlorophyll breaks down, "
        "so yellow and orange pigments that were hidden all summer finally show."
    ),
}


def load_example() -> None:
    name = st.session_state.get("plag_example")
    if name in EXAMPLES:
        st.session_state["plag_source"] = EXAMPLE_SOURCE
        st.session_state["plag_submission"] = EXAMPLES[name]


def gauge_html(similarity: float) -> str:
    pct = round(similarity * 100)
    if pct < 20:
        color, verdict = "#4ade80", "Mostly unique"
    elif pct < 50:
        color, verdict = "#f59e0b", "Some matching text"
    else:
        color, verdict = "#F05252", "High similarity"
    return (
        f'<div style="text-align:center;margin:.4rem 0 .2rem">'
        f'<div style="font-size:3rem;font-weight:800;color:{color};line-height:1">{pct}%</div>'
        f'<div style="color:{color};font-weight:600;margin:.3rem 0 .7rem">{verdict}</div></div>'
        f'<div style="background:rgba(255,255,255,.08);border-radius:999px;height:12px;overflow:hidden">'
        f'<div style="width:{pct}%;height:100%;background:{color}"></div></div>'
    )


def quick_tab() -> None:
    c1, c2, c3 = st.columns([1, 1, 1], vertical_alignment="bottom")
    c1.selectbox("Load an example", ["—", *EXAMPLES], key="plag_example", on_change=load_example)
    st.session_state.setdefault("plag_n", 4)
    n = c2.slider("Strictness (n-gram size)", 3, 8, key="plag_n",
                  help="How many words in a row must match. Lower is stricter and catches shorter copied phrases.")
    st.session_state.setdefault("plag_cite", "(Source)")
    cite = c3.text_input("Cite the source as", key="plag_cite", placeholder="(Wikipedia, 2024)",
                         help="Added after each copied passage in the final text, e.g. (Wikipedia, 2024) or [1].")

    left, right = st.columns(2)
    with left:
        st.markdown("#### Source / Reference Text")
        source = st.text_area("Source", key="plag_source", height=240, label_visibility="collapsed",
                              placeholder="Paste the original text...")
        counter(source)
    with right:
        st.markdown("#### Submitted Text")
        submission = st.text_area("Submission", key="plag_submission", height=240, label_visibility="collapsed",
                                  placeholder="Paste the text to check...")
        counter(submission)

    b1, b2, _ = st.columns([2, 1, 1])
    go = b1.button("Check Plagiarism", key="plag_quick", type="primary", icon=":material/plagiarism:", width="stretch")
    b2.button("Clear All", key="clear_quick", icon=":material/delete:", width="stretch",
              on_click=clear_keys, args=("plag_source", "plag_submission"))

    if not go:
        return
    if not source.strip() or not submission.strip():
        st.warning("Add both the source and the submitted text first.")
        return

    r = quick_check(source, submission, n)
    st.divider()
    g, m1, m2, m3 = st.columns([2, 1, 1, 1], vertical_alignment="center")
    g.markdown(gauge_html(r.similarity), unsafe_allow_html=True)
    m1.metric("Matched words", f"{r.matched} / {r.total}")
    m2.metric("Analysis mode", f"{n}-gram match")
    m3.metric("Sequence match (difflib)", f"{r.sequence_ratio:.0%}",
              help="Python's difflib ratio of the two word sequences. It only counts text in the same order, "
                   "so it drops when copied parts are moved around.")

    st.markdown(legend_html(["match"]), unsafe_allow_html=True)
    h1, h2 = st.columns(2)
    h1.markdown("##### Source")
    h1.markdown(render_html(source, [(s, e, "match") for s, e in r.spans_source]), unsafe_allow_html=True)
    h2.markdown("##### Submission")
    h2.markdown(render_html(submission, [(s, e, "match") for s, e in r.spans_submission]), unsafe_allow_html=True)
    st.caption("Matching ignores capital letters and punctuation. Reworded text with the same meaning isn't caught, "
               "and a quoted, cited passage still shows as a match.")

    if r.spans_submission:
        st.markdown(f"**Identical phrase sequences ({len(r.spans_submission)})**")
        rows = [(submission[s:e], len(submission[s:e].split())) for s, e in r.spans_submission]
        rows.sort(key=lambda row: row[1], reverse=True)
        st.markdown(
            "| # | Phrase | Words |\n|---|---|---|\n"
            + "\n".join(f"| {i} | {md_cell(p)} | {w} |" for i, (p, w) in enumerate(rows, 1))
        )
        final_output(
            "quick", "Final Text: copied parts quoted and cited",
            quote_and_cite(submission, [(s, e, cite.strip()) for s, e in r.spans_submission]),
            "Each copied passage is now in quotation marks with your citation, so it's credited. A few short "
            "quotes are fine, but most of an essay should be in your own words: rewrite long passages instead.",
            "final-text.txt",
        )


def md_cell(text: str) -> str:
    """Make text safe inside a Markdown table cell."""
    return " ".join(text.split()).replace("\\", "\\\\").replace("|", "\\|").replace("<", "&lt;")


def read_sources(files, pasted: str) -> dict[str, str]:
    sources: dict[str, str] = {}
    for f in files or []:
        try:
            sources[f.name] = extract_text(f.name, f.getvalue())
        except DocumentError as exc:
            st.error(f"{f.name}: {exc}")
    if pasted.strip():
        sources["Pasted source"] = pasted
    return sources


def multi_tab() -> None:
    st.write(
        f"Check a whole draft against several sources. Passages of {MATCH_WORDS}+ matching words are "
        "**green** if quoted or cited and **red** if not."
    )
    st.markdown("#### Your Draft")
    draft = st.text_area("Your draft", key="plag_draft", height=280, label_visibility="collapsed",
                         placeholder="Paste your essay or paper here...")
    counter(draft)
    upload = st.file_uploader(f"...or upload your draft ({FILE_TYPES})", type=list(SUPPORTED), key="plag_draft_file")
    if upload is not None:
        try:
            draft = extract_text(upload.name, upload.getvalue())
        except DocumentError as exc:
            st.error(str(exc))
        else:
            st.caption(f"Using **{upload.name}** ({len(draft.split()):,} words) instead of the box above.")

    st.markdown("#### Sources")
    files = st.file_uploader(f"Upload up to {MAX_SOURCES} source files ({FILE_TYPES})", type=list(SUPPORTED),
                             accept_multiple_files=True, key="plag_sources")
    pasted = st.text_area("...and/or paste a source", key="plag_source_text", height=150,
                          placeholder="Paste an article, web page or book passage you used...")

    b1, b2, _ = st.columns([2, 1, 1])
    go = b1.button("Check Against All Sources", key="plag_check", type="primary", icon=":material/plagiarism:", width="stretch")
    b2.button("Clear All", key="clear_plag", icon=":material/delete:", width="stretch",
              on_click=clear_keys, args=("plag_draft", "plag_source_text"))

    if not go:
        return
    sources = read_sources(files, pasted)
    if not draft.strip():
        st.warning("Add your draft first.")
        return
    if not sources:
        st.warning("Add at least one source to check against.")
        return
    if len(sources) > MAX_SOURCES:
        st.warning(f"Only the first {MAX_SOURCES} sources are checked.")

    r = check(draft, sources)
    st.divider()
    matched_sources = sum(1 for s in r.sources if s.matches)
    c1, c2, c3 = st.columns(3)
    c1.metric("Matches a source", f"{r.coverage:.0%}", help="Share of your draft's words inside passages found in a source.")
    c2.metric("Not cited", f"{r.uncited_coverage:.0%}", help="Matching words that are neither in quotation marks nor in a sentence with a citation.")
    c3.metric("Sources matched", f"{matched_sources} of {len(r.sources)}")

    if not r.matches:
        st.success(f"No passages of {MATCH_WORDS}+ words match your sources.")
        return
    if r.uncited_coverage:
        card("plagiarism", f"{r.uncited_coverage:.0%} of your draft matches a source without a citation",
             "quote and cite those passages, or rewrite the idea in your own words and still cite the source")
    else:
        st.success("Every matching passage is quoted or cited.")

    st.markdown("**By source**")
    st.markdown(
        "| Source | Words | Matches your draft | Passages |\n|---|---|---|---|\n"
        + "\n".join(f"| {s.name} | {s.words:,} | {s.coverage:.0%} | {s.matches} |" for s in r.sources)
    )

    st.markdown("**Your draft**")
    spans = [(m.start, m.end, "cited" if m.cited else "uncited") for m in r.matches]
    st.markdown(legend_html(["uncited", "cited"]), unsafe_allow_html=True)
    st.markdown(render_html(draft, spans), unsafe_allow_html=True)

    with st.expander(f"All {len(r.matches)} matching passages"):
        for m in r.matches:
            status = ":green[quoted or cited]" if m.cited else ":red[not cited]"
            st.markdown(f"**{m.source}** · {status}")
            st.info(draft[m.start : m.end])

    if r.uncited_coverage:
        final_output(
            "multi", "Final Text: uncited passages quoted and cited",
            quote_and_cite(draft, [(m.start, m.end, f"({m.source})") for m in r.matches if not m.cited]),
            "Each uncited match is now in quotation marks followed by its source's name. Replace the name with a "
            "proper citation (e.g. from the Citations tab), or rewrite long passages in your own words.",
            "final-draft.txt",
        )


def render() -> None:
    st.markdown("### :material/plagiarism: Plagiarism Checker")
    tab_quick, tab_multi = st.tabs(["Quick check (two texts)", "Multiple sources"])
    with tab_quick:
        quick_tab()
    with tab_multi:
        multi_tab()
