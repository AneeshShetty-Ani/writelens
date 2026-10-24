import html

import streamlit as st

from auth import require_login, sign_out
from ui import about_page, checker_page, citations_page, feedback_page, plagiarism_page, similarity_page
from ui.theme import VERSION, apply_css, banner

# key -> (top navigation label, icon)
PAGES = {
    "checker": ("Writing", ":material/edit_note:"),
    "plagiarism": ("Plagiarism", ":material/plagiarism:"),
    "citations": ("Citations", ":material/format_quote:"),
    "similarity": ("Compare", ":material/compare_arrows:"),
    "feedback": ("Feedback", ":material/feedback:"),
    "about": ("How it works", ":material/help:"),
}
# Streamlit deletes the state of widgets that aren't drawn, so text typed on one page would be
# lost after visiting another. Re-assigning these keys every run keeps them.
PERSISTENT_KEYS = (
    "checker_text", "word_limit", "plag_source", "plag_submission", "plag_n", "plag_cite", "plag_draft", "plag_source_text",
    "cite_style", "cite_text", "doc_a", "doc_b",
)
VERSION_HISTORY = [
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
    ("Spelling", "probable typos underlined, with the fix (recieve → receive)"),
    ("Formal tone", "casual words (gonna, stuff, a lot of) with formal choices, and essays that keep saying “you”"),
    ("Sentence starts", "spots three or more sentences in a row that begin with the same word"),
    ("Always tested", "every update runs all the tests automatically on GitHub"),
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

with st.container(key="topnav", horizontal=True, gap="small"):
    for key, (label, icon) in PAGES.items():
        st.button(label, key=f"nav_{key}", icon=icon,
                  type="primary" if key == page else "secondary", on_click=go_to, args=(key,))

if page == "checker":
    checker_page.render()
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
