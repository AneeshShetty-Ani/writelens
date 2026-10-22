import streamlit as st

from analysis import LONG_SENTENCE_WORDS
from score import WEIGHTS
from similarity import MATCH_WORDS, NGRAM

# (title, icon, explanation)
SECTIONS = [
    ("Writing Checker", ":material/edit_note:", f"""
- **Wordy phrases**: a list of about 25 phrases with shorter versions (*due to the fact that → because*). The
  longest phrase is matched first so the same words are never counted twice.
- **Long sentences**: sentences over {LONG_SENTENCE_WORDS} words. Sentences are split at `. ! ?` and line breaks,
  ignoring abbreviations like *Dr.* and *e.g.*
- **Passive voice, weak verbs, filler adverbs, repeated words**: found with **spaCy**, an NLP library that tags
  each word's part of speech and grammar role. A sentence is passive when spaCy finds a passive subject or
  passive helper verb (`nsubjpass` / `auxpass`), as in *the report **was written***.
- **Reading ease and grade level**: the Flesch and Flesch-Kincaid formulas, which use average sentence length
  and syllables per word.
- **Writing score**: starts at 100 and loses points per 100 words for each issue
  ({", ".join(f"{k.replace('_', ' ')} −{v}" for k, v in WEIGHTS.items())}), plus a little more if the text is
  hard to read. Measuring per 100 words means a long essay isn't punished just for being long.
"""),
    ("Plagiarism Checker", ":material/plagiarism:", f"""
- Both texts are lower-cased and split into words, then into **n-grams** (runs of *n* words in a row, default 4).
- **Similarity** = the share of the submitted text's words that sit inside an n-gram also found in the source.
- **Sequence match** uses Python's `difflib`, which finds the longest matching blocks in the same order.
- With several sources, passages of {MATCH_WORDS}+ matching words are marked **cited** if they're in quotation
  marks or in a sentence with a citation such as `[1]`, `(Smith, 2020)` or `[@key]`, and **not cited**
  otherwise.
- It only compares against sources you give it; it doesn't search the internet.
"""),
    ("Citations", ":material/format_quote:", """
- **DOI lookup** asks the free Crossref API for the title, authors, journal and year.
- References are formatted in **IEEE, APA, MLA or Harvard** style.
- Write `[@key]` in your text; WriteLens replaces each marker with a formatted citation, builds the reference
  list, and exports **BibTeX (.bib)**, **CSL-JSON** (works with Zotero and Mendeley) and **LaTeX `\\cite`**.
"""),
    ("Compare", ":material/compare_arrows:", f"""
- **N-gram overlap (Jaccard)**: shared {NGRAM}-word runs divided by all {NGRAM}-word runs in either document.
- **Winnowing fingerprints**: the method used by the Stanford MOSS plagiarism detector. Each document is
  hashed into fingerprints, and the share of fingerprints they have in common is reported.
- **Cosine similarity**: compares how often each word is used, so it notices a shared topic even when the
  wording differs.
- Matching passages of {MATCH_WORDS}+ words are highlighted in both documents, even if they were moved around.
"""),
    ("Sign-in and privacy", ":material/lock:", """
- Sign-in uses **GitHub OAuth**. After login, the server asks GitHub whether you've starred the WriteLens
  repo and follow its author; only public information is read, and your GitHub sign-in is discarded
  once the check passes.
- Your text is processed in memory and is not saved anywhere. Refreshing the page signs you out.
"""),
]


def render() -> None:
    st.markdown("### :material/help: How it works")
    st.write("Every check runs on the server with open-source Python, so no text is sent to an AI service.")
    for title, icon, body in SECTIONS:
        with st.expander(f"{icon} **{title}**", expanded=title == "Writing Checker"):
            st.markdown(body)
    st.caption("Built with Python, Streamlit, spaCy, difflib, requests (Crossref API) and python-docx.")
