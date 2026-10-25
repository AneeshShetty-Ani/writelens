import html

import streamlit as st

from auth import require_login, sign_out
from ui import (
    about_page, assignment_page, checker_page, citations_page, engine, feedback_page, plagiarism_page,
    similarity_page,
)
from ui.theme import VERSION, apply_css, banner

# key -> (top navigation label, icon)
PAGES = {
    "checker": ("Writing", ":material/edit_note:"),
    "assignment": ("Assignment", ":material/assignment:"),
    "plagiarism": ("Plagiarism", ":material/plagiarism:"),
    "citations": ("Citations", ":material/format_quote:"),
    "similarity": ("Compare", ":material/compare_arrows:"),
    "feedback": ("Feedback", ":material/feedback:"),
    "about": ("How it works", ":material/help:"),
}
# Streamlit deletes the state of widgets that aren't drawn, so text typed on one page would be
# lost after visiting another. Re-assigning these keys every run keeps them.
PERSISTENT_KEYS = (
    "checker_text", "word_limit", "writing_mode", "assign_prompt", "assign_text", "plag_source", "plag_submission", "plag_n", "plag_cite", "plag_draft", "plag_source_text",
    "cite_style", "cite_text", "doc_a", "doc_b",
)
VERSION_HISTORY = [
    ("1.7.0", "hybrid AI engine: every tool uses free AI models when available and runs offline otherwise, "
              "long texts are checked by AI in parts, offline reference reading, AI engine status light"),
    ("1.6.0", "Assignment Checker with an improved version, writing modes, reverse outline, word budget, reader effort map, "
              "listen to your text, weak openings and conclusions, “Why?” lessons, fix pasted text, book "
              "citations by ISBN"),
    ("1.5.0", "spelling mistakes, informal words and talking to the reader, repeated sentence starts, "
              "automatic tests on GitHub"),
    ("1.4.0", "PDF upload, report download as PDF and Word, cliché / contraction / mixed UK-US spelling checks, "
              "reading and speaking time, stay signed in after a refresh, score change between drafts, word limit, "
              "sentence-length chart, Chicago citations, contractions expanded in Improved Text"),
    ("1.3.0", "Writing score and grade level, one-click sample text, How it works page, new sign-in screen"),
    ("1.2.0", "Frosted Obsidian theme, top navigation instead of a sidebar, single-column layout with issues in a grid below the text"),
    ("1.1.0", "Nordic Indigo theme with glowing-outline cards, colour-coded issue cards, 60/40 workspace layout, difflib sequence score"),
    ("1.0.1", "Plagiarism Checker (quick two-text check and multiple sources), issues shown as alerts, text kept between pages"),
    ("1.0", "Dark hub layout, inline highlights, citations, pairwise similarity, feedback form"),
    ("0.4", "GitHub sign-in with an allow-list"),
    ("0.3", "Document upload (.docx, .tex, .md, .txt) and Markdown reports"),
    ("0.2", "spaCy checks: passive voice, repeated words, weak verbs, filler adverbs"),
    ("0.1", "Readability stats, wordy phrases, long sentences"),
]
WHATS_NEW = [
    ("Hybrid AI engine", "every tool uses AI when it's available and works offline when it isn't; long texts "
                         "are checked in full, in parts"),
    ("Writing", "AI finds grammar and clarity problems the rules miss, and polishes the Improved Text"),
    ("Assignment", "AI judges each requirement by meaning and gives specific hints"),
    ("Plagiarism and Compare", "AI also catches reworded (paraphrased) passages"),
    ("Citations", "paste a reference written any way; AI reads it and Crossref checks it's real, and standard "
                  "styles are read offline too. AI finds a website's hidden author or date"),
    ("Feedback", "AI tidies your report into a clear GitHub issue"),
    ("Status light", "under your name: green online, yellow maintenance, red stopped, grey offline"),
]

st.set_page_config(page_title="WriteLens", page_icon="🔍", layout="wide", initial_sidebar_state="collapsed")
apply_css()

user = require_login()


def go_to(page: str) -> None:
    st.session_state["page"] = page


for key in PERSISTENT_KEYS:
    if key in st.session_state:
        st.session_state[key] = st.session_state[key]

page = st.session_state.setdefault("page", "checker")

brand, account = st.columns([4, 1], vertical_alignment="center")
with brand:
    banner()
with account.popover(user, icon=":material/account_circle:", width="stretch"):
    st.caption(f"Signed in with GitHub as **{html.escape(user)}**")
    st.button("Logout", key="logout", icon=":material/logout:", width="stretch", on_click=sign_out)
    st.markdown(f"**:material/bolt: New in v{VERSION}**")
    st.markdown("\n".join(f"- **{name}**: {desc}" for name, desc in WHATS_NEW))
    with st.expander(":material/history: Version history"):
        st.markdown("\n".join(f"- **v{v}**: {desc}" for v, desc in VERSION_HISTORY))
# filled in after the page, so it shows how the AI did on this run
ai_status = account.empty()

with st.container(key="topnav", horizontal=True, gap="small"):
    for key, (label, icon) in PAGES.items():
        st.button(label, key=f"nav_{key}", icon=icon,
                  type="primary" if key == page else "secondary", on_click=go_to, args=(key,))

if page == "checker":
    checker_page.render()
elif page == "assignment":
    assignment_page.render()
elif page == "plagiarism":
    plagiarism_page.render()
elif page == "citations":
    citations_page.render()
elif page == "similarity":
    similarity_page.render()
elif page == "about":
    about_page.render()
else:
    feedback_page.render(user)

engine.render_status(ai_status)
