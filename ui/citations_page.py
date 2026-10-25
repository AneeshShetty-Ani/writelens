import streamlit as st

from citations import (
    KINDS, STYLES, CitationError, Reference, format_entry, from_csl_json, insert_citations,
    lookup_doi, lookup_isbn, make_key, reference_list, to_bibtex, to_csl_json,
)
from documents import SUPPORTED, DocumentError, extract_text
from ui.theme import clear_keys, counter
from webcite import lookup_url

CONTAINER_LABEL = {"article": "Journal", "book": "Publisher", "web": "Website name"}


def refs() -> list[Reference]:
    return st.session_state.setdefault("refs", [])


def keys() -> set[str]:
    return {r.key for r in refs()}


def add_doi() -> None:
    try:
        ref = lookup_doi(st.session_state.get("doi_input", ""), keys())
    except CitationError as exc:
        st.session_state["cite_msg"] = ("error", str(exc))
    else:
        refs().append(ref)
        st.session_state["doi_input"] = ""
        st.session_state["cite_msg"] = ("success", f"Added **{ref.title}** as `[@{ref.key}]`.")


def add_isbn() -> None:
    try:
        ref = lookup_isbn(st.session_state.get("isbn_input", ""), keys())
    except CitationError as exc:
        st.session_state["cite_msg"] = ("error", str(exc))
    else:
        refs().append(ref)
        st.session_state["isbn_input"] = ""
        st.session_state["cite_msg"] = ("success", f"Added **{ref.title}** as `[@{ref.key}]`.")


def add_url() -> None:
    try:
        ref = lookup_url(st.session_state.get("url_input", ""), keys())
    except CitationError as exc:
        st.session_state["cite_msg"] = ("error", str(exc))
    else:
        refs().append(ref)
        st.session_state["url_input"] = ""
        missing = [label for label, value in (("author", ref.authors), ("year", ref.year)) if not value]
        note = f" The page doesn't list a {' or '.join(missing)}; that's normal for many websites." if missing else ""
        st.session_state["cite_msg"] = ("success", f"Added **{ref.title}** as `[@{ref.key}]`.{note}")


def remove_ref(key: str) -> None:
    st.session_state["refs"] = [r for r in refs() if r.key != key]


def load_document(name: str, data: bytes) -> None:
    try:
        st.session_state["cite_text"] = extract_text(name, data)
    except DocumentError as exc:
        st.session_state["cite_msg"] = ("error", str(exc))


def manual_form() -> None:
    kind = st.radio("Type", list(KINDS), format_func=KINDS.get, horizontal=True, key="manual_kind")
    with st.form("manual_ref", clear_on_submit=True, border=False):
        authors = st.text_area("Authors (one per line, as Family, Given)", placeholder="Smith, Jane\nLee, Anna", height=90)
        title = st.text_input("Title")
        c1, c2 = st.columns([3, 1])
        container = c1.text_input(CONTAINER_LABEL[kind])
        year = c2.text_input("Year")
        if kind == "article":
            c3, c4, c5 = st.columns(3)
            volume, issue, pages = c3.text_input("Volume"), c4.text_input("Issue"), c5.text_input("Pages")
        else:
            volume = issue = pages = ""
        c6, c7 = st.columns(2)
        doi, url = c6.text_input("DOI (optional)"), c7.text_input("URL (optional)")
        if st.form_submit_button("Add reference", icon=":material/add:"):
            if not title.strip():
                st.error("A title is required.")
                return
            author_list = [a.strip() for a in authors.splitlines() if a.strip()]
            ref = Reference(
                key=make_key(author_list, year.strip(), keys()), kind=kind, title=title.strip(),
                authors=author_list, year=year.strip(), container=container.strip(), volume=volume.strip(),
                issue=issue.strip(), pages=pages.strip(), doi=doi.strip(), url=url.strip(),
            )
            refs().append(ref)
            st.success(f"Added as `[@{ref.key}]`.")


def render() -> None:
    st.markdown("### :material/format_quote: Citation Inserter & BIB / JSON / LaTeX")
    st.write(
        "Add the sources you used, put `[@key]` in your text where each one supports a point, and get "
        "formatted citations, a reference list, and BibTeX (`.bib`), LaTeX (`\\cite{key}`) and JSON exports."
    )

    style = st.selectbox("Citation Format", STYLES, key="cite_style")

    st.markdown("#### 1. Your references")
    tab_url, tab_doi, tab_isbn, tab_manual, tab_import = st.tabs(
        ["Cite a website", "Look up DOI", "Book (ISBN)", "Enter manually", "Import JSON"])
    with tab_url:
        c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
        c1.text_input("Web page address", key="url_input", placeholder="e.g. https://en.wikipedia.org/wiki/Photosynthesis")
        c2.button("Fetch details", key="url_lookup", on_click=add_url, icon=":material/language:", width="stretch")
        st.caption("Reads the page's title, author, date and site name for you. Check them before you submit.")
    with tab_doi:
        c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
        c1.text_input("DOI", key="doi_input", placeholder="e.g. 10.1038/nature14539 or https://doi.org/...")
        c2.button("Look up", key="doi_lookup", on_click=add_doi, icon=":material/search:", width="stretch")
    with tab_isbn:
        c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
        c1.text_input("ISBN", key="isbn_input", placeholder="e.g. 978-0-14-143951-8 (on the back cover or copyright page)")
        c2.button("Look up", key="isbn_lookup", on_click=add_isbn, icon=":material/menu_book:", width="stretch")
        st.caption("Finds the title, authors, publisher and year in Open Library, a free catalogue of books. "
                   "Check them against your copy, since editions differ.")
    with tab_manual:
        manual_form()
    with tab_import:
        upload = st.file_uploader("CSL-JSON file (e.g. one exported from here, Zotero or Mendeley)", type=["json"])
        if upload is not None and st.button("Import references", key="import_refs"):
            try:
                new = from_csl_json(upload.getvalue().decode("utf-8", errors="replace"), keys())
            except CitationError as exc:
                st.error(str(exc))
            else:
                refs().extend(new)
                st.success(f"Imported {len(new)} reference(s).")

    if msg := st.session_state.pop("cite_msg", None):
        getattr(st, msg[0])(msg[1])

    if not refs():
        st.caption("No references yet.")
    for ref in refs():
        with st.container(border=True):
            c1, c2 = st.columns([12, 1], vertical_alignment="center")
            c1.markdown(f"`[@{ref.key}]` &nbsp; {format_entry(ref, style)}")
            c2.button("", key=f"rm_{ref.key}", icon=":material/close:", help="Remove", on_click=remove_ref, args=(ref.key,))
    if refs():
        d1, d2 = st.columns(2)
        d1.download_button("Download all as BibTeX (.bib)", to_bibtex(refs()), "references.bib", "text/x-bibtex",
                           icon=":material/download:", width="stretch", on_click="ignore")
        d2.download_button("Download all as JSON (CSL)", to_csl_json(refs()), "references.json", "application/json",
                           icon=":material/download:", width="stretch", on_click="ignore")

    st.markdown("#### 2. Insert citations")
    st.caption("Example: `Deep learning changed image recognition [@lecun2015]. Others disagree [@smith2020; @lee2019].`")
    with st.expander("Load text from a document"):
        doc = st.file_uploader("Document", type=list(SUPPORTED), key="cite_doc", label_visibility="collapsed")
        if doc is not None:
            st.button("Load into the editor", key="load_doc", on_click=load_document, args=(doc.name, doc.getvalue()))

    st.markdown("##### Input Text")
    text = st.text_area("Input text", key="cite_text", height=320, label_visibility="collapsed",
                        placeholder="Paste your essay or paper and add [@key] markers...")
    counter(text)
    b_go, b_clear, _ = st.columns([2, 1, 1])
    go = b_go.button("Insert Citations", key="insert_citations", type="primary", icon=":material/format_quote:", width="stretch")
    b_clear.button("Clear All", key="clear_cite", icon=":material/delete:", width="stretch", on_click=clear_keys, args=("cite_text",))

    st.markdown("##### Text with Inserted Citations")
    if not (go and text.strip()):
        st.markdown('<div class="uf-placeholder">Insert citations to see the result here.</div>', unsafe_allow_html=True)
        return

    result = insert_citations(text, refs(), style)
    entries = reference_list(result.used, style)
    st.text_area("Output", result.text, height=320, label_visibility="collapsed")
    counter(result.text)
    if result.unknown:
        st.warning("These keys don't match any reference, so they were left as they are: "
                   + ", ".join(f"`{k}`" for k in result.unknown))
    if not result.used:
        st.info("No `[@key]` markers matched your references.")
        return

    st.markdown(f"**References ({style})**")
    for entry in entries:
        st.markdown(entry)

    document = result.text + "\n\n## References\n\n" + "\n\n".join(entries) + "\n"
    latex = result.latex + "\n\n\\bibliographystyle{" + ("ieeetr" if style == "IEEE" else "apalike") + "}\n\\bibliography{references}\n"
    d1, d2, d3 = st.columns(3)
    d1.download_button("Text + references (.md)", document, "cited-text.md", "text/markdown",
                       icon=":material/download:", width="stretch", on_click="ignore")
    d2.download_button("LaTeX with \\cite (.tex)", latex, "cited-text.tex", "application/x-tex",
                       icon=":material/download:", width="stretch", on_click="ignore")
    d3.download_button("Cited references (.bib)", to_bibtex(result.used), "references.bib", "text/x-bibtex",
                       icon=":material/download:", width="stretch", on_click="ignore")
