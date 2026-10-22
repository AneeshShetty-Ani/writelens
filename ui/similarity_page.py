import streamlit as st

from documents import SUPPORTED, DocumentError, extract_text
from highlight import legend_html, render_html
from similarity import MATCH_WORDS, NGRAM, compare
from ui.theme import clear_keys, counter, final_output


def document_input(label: str, key: str) -> str:
    st.markdown(f"#### {label}")
    text = st.text_area(label, key=key, height=280, label_visibility="collapsed", placeholder=f"Paste text for {label.split(' (')[0]} here...")
    counter(text)
    upload = st.file_uploader(f"...or upload a file ({', '.join('.' + e for e in SUPPORTED)})", type=list(SUPPORTED), key=f"{key}_file")
    if upload is not None:
        try:
            text = extract_text(upload.name, upload.getvalue())
        except DocumentError as exc:
            st.error(str(exc))
        else:
            st.caption(f"Using **{upload.name}** ({len(text.split()):,} words) instead of the box above.")
    return text


def summary(r) -> str:
    """The comparison in plain sentences, ready to paste into notes or a report."""
    overlap = max(r.coverage_a, r.coverage_b)
    if overlap >= 0.5:
        verdict = "The documents share large parts of their text word for word."
    elif overlap >= 0.15:
        verdict = "The documents share some passages word for word."
    elif r.cosine >= 0.5:
        verdict = "The documents cover a similar topic but are written in different words."
    else:
        verdict = "The documents are largely different."
    lines = [
        verdict,
        f"{r.coverage_a:.0%} of Document A ({r.words_a:,} words) appears in Document B, and "
        f"{r.coverage_b:.0%} of Document B ({r.words_b:,} words) appears in Document A.",
        f"Shared passages of {MATCH_WORDS}+ words: {len(r.passages)}. Fingerprint match: {r.fingerprint_match:.0%}. "
        f"Word-use similarity: {r.cosine:.0%}.",
    ]
    if r.passages:
        lines += ["", "Shared passages:"] + [f"- {p}" for p in r.passages]
    return "\n".join(lines)


def render() -> None:
    st.markdown("### :material/compare_arrows: Pairwise Document Similarity Checker")
    st.write(
        f"Compare two documents side by side: exact {NGRAM}-word n-gram overlap, winnowing fingerprints, "
        f"word-frequency similarity, and the passages ({MATCH_WORDS}+ identical words in a row) they share."
    )

    left, right = st.columns(2)
    with left:
        text_a = document_input("Document A (Your Text / Draft)", "doc_a")
    with right:
        text_b = document_input("Document B (Source / Reference)", "doc_b")

    b1, b2 = st.columns(2)
    go = b1.button("Compare Document A vs Document B", key="compare", type="primary", icon=":material/compare_arrows:", width="stretch")
    b2.button("Clear All", key="clear_compare", icon=":material/delete:", width="stretch", on_click=clear_keys, args=("doc_a", "doc_b"))

    if not go:
        return
    if not text_a.strip() or not text_b.strip():
        st.warning("Add text for both documents first.")
        return

    r = compare(text_a, text_b)
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("A found in B", f"{r.coverage_a:.0%}", help="Share of Document A's words inside passages that also appear in B.")
    c2.metric("B found in A", f"{r.coverage_b:.0%}", help="Share of Document B's words inside passages that also appear in A.")
    c3.metric("Fingerprint match", f"{r.fingerprint_match:.0%}", help="Winnowing: share of the shorter document's fingerprints also in the other.")
    c4.metric("Word similarity", f"{r.cosine:.0%}", help="Cosine similarity of word counts (ignoring common words). High for documents on the same topic.")
    st.caption(f"{NGRAM}-gram Jaccard overlap: {r.ngram_jaccard:.1%} · Sequence match (difflib): {r.sequence_ratio:.1%} · Document A: {r.words_a:,} words · Document B: {r.words_b:,} words")

    if not r.passages:
        st.success(f"No shared passages of {MATCH_WORDS}+ words found.")
    else:
        st.markdown(f"**{len(r.passages)} matching passage(s)** highlighted below.")
        st.markdown(legend_html(["match"]), unsafe_allow_html=True)
        h1, h2 = st.columns(2)
        h1.markdown("##### Document A")
        h1.markdown(render_html(text_a, [(s, e, "match") for s, e in r.spans_a]), unsafe_allow_html=True)
        h2.markdown("##### Document B")
        h2.markdown(render_html(text_b, [(s, e, "match") for s, e in r.spans_b]), unsafe_allow_html=True)

        with st.expander("List of matching passages"):
            for p in r.passages:
                st.info(p)

    final_output("compare", "Summary", summary(r), file_name="comparison-summary.txt")
