import re

import streamlit as st

from ai_tasks import accept_citation, accept_web_details, citation_task, family, web_details_task
from citations import (
    DOI_IN_TEXT, ISBN_IN_TEXT, KINDS, STYLES, CitationError, Reference, crossref_search, format_entry,
    from_csl_json, from_fields, insert_citations, lookup_doi, lookup_isbn, make_key, parse_reference,
    reference_list, to_bibtex, to_csl_json,
)
from documents import SUPPORTED, DocumentError, extract_text
from ui import engine
from ui.theme import clear_keys, counter
from webcite import page_reference, read_page

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


def cite_page(url: str) -> tuple[Reference, str]:
    """(the reference for a web page, a note on what the AI added). When the page's metadata has no author
    or date, the AI looks for them in the page's text; it can only use names and years printed there."""
    info = read_page(url)
    missing = [k for k in ("authors", "year") if not info[k]]
    if not missing or not info["text"]:
        return page_reference(info, keys()), ""
    answer = engine.run("webpage", web_details_task(info["title"], info["text"]), accept_web_details(info["text"]),
                        info["url"], info["text"])
    if not answer:
        st.session_state.pop("ai_skipped", None)  # the page's own details are used, as offline
        return page_reference(info, keys()), ""
    found = [k for k in missing if answer.data[k]]
    for k in found:
        info[k] = answer.data[k]
    words = {"authors": "author", "year": "date"}
    note = (f" AI ({engine.by_line(answer)}) found the {' and '.join(words[k] for k in found)} in the page's text."
            if found else "")
    return page_reference(info, keys()), note


def add_url() -> None:
    try:
        ref, note = cite_page(st.session_state.get("url_input", ""))
    except CitationError as exc:
        st.session_state["cite_msg"] = ("error", str(exc))
    else:
        refs().append(ref)
        st.session_state["url_input"] = ""
        missing = [label for label, value in (("author", ref.authors), ("year", ref.year)) if not value]
        if missing:
            note += f" The page doesn't list a {' or '.join(missing)}; that's normal for many websites."
        st.session_state["cite_msg"] = ("success", f"Added **{ref.title}** as `[@{ref.key}]`.{note}")


def resolve_reference(text: str) -> tuple[Reference, str]:
    """(the reference, how it was found) for a reference written any way. Exact identifiers first, then the
    AI reads it and Crossref checks it; without the AI, Crossref is searched with the text itself, and
    without Crossref either, the reference is read offline from its punctuation (APA, MLA and so on)."""
    if m := DOI_IN_TEXT.search(text):
        return lookup_doi(m.group().rstrip(".,;)"), keys()), "found by its DOI"
    if m := ISBN_IN_TEXT.search(text):
        return lookup_isbn(m.group(1), keys()), "found by its ISBN"
    if re.fullmatch(r"https?://\S+", text):
        ref, note = cite_page(text)
        return ref, "read from the web page" + (f".{note.rstrip('.')}" if note else "")
    answer = engine.run("citation", citation_task(text), accept_citation(text), text)
    if answer:
        fields = answer.data
        query = " ".join([fields["title"], *(family(a) for a in fields["authors"][:2]), fields["year"]])
        if ref := crossref_search(query, keys(), check_against=text, year=fields["year"]):
            return ref, f"read by AI ({engine.by_line(answer)}) and matched to its Crossref record"
        return (from_fields(fields, keys()), f"read by AI ({engine.by_line(answer)}); it isn't in Crossref (normal "
                "for many books and websites), so check the details")
    st.session_state.pop("ai_skipped", None)  # the messages below say how it was read instead
    parsed = parse_reference(text)
    if ref := crossref_search(text, keys(), year=parsed["year"] if parsed else ""):
        return ref, "found in Crossref"
    if parsed:
        return from_fields(parsed, keys()), "read offline from how it's written, so check the details"
    raise CitationError("Couldn't recognise that reference" + (" (the AI is unavailable right now)" if engine.available()
                        else "") + ". Write it in a standard style such as APA or MLA, use its DOI or ISBN, or "
                        "enter it manually.")


def add_any() -> None:
    text = " ".join(st.session_state.get("any_input", "").split())
    if not text:
        st.session_state["cite_msg"] = ("warning", "Paste a reference first.")
        return
    try:
        ref, how = resolve_reference(text)
    except CitationError as exc:
        st.session_state["cite_msg"] = ("error", str(exc))
    else:
        refs().append(ref)
        st.session_state["any_input"] = ""
        st.session_state["cite_msg"] = ("success", f"Added **{ref.title}** as `[@{ref.key}]`: {how}.")


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
    tab_any, tab_url, tab_doi, tab_isbn, tab_manual, tab_import = st.tabs(
        ["Paste any reference", "Cite a website", "Look up DOI", "Book (ISBN)", "Enter manually", "Import JSON"])
    with tab_any:
        st.text_area("Reference", key="any_input", height=90, label_visibility="collapsed",
                     placeholder="Paste a reference in any style, even a messy one, e.g.\n"
                                 "lecun bengio hinton 2015 deep learning nature")
        st.button("Read reference", key="any_lookup", on_click=add_any, icon=":material/auto_awesome:")
        st.caption("A DOI, ISBN or web address is looked up directly. Otherwise AI reads the reference (when "
                   "available) and Crossref, a free database of published works, checks it's real. Without "
                   "either, a reference in a standard style (APA, MLA, Harvard, Chicago, IEEE) is read offline.")
    with tab_url:
        c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
        c1.text_input("Web page address", key="url_input", placeholder="e.g. https://en.wikipedia.org/wiki/Photosynthesis")
        c2.button("Fetch details", key="url_lookup", on_click=add_url, icon=":material/language:", width="stretch")
        st.caption("Reads the page's title, author, date and site name for you; when the page hides its author or "
                   "date, AI looks for them in the text. Check them before you submit.")
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
