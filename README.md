# WriteLens

A Streamlit writing assistant: paste text or upload a document (`.docx`, `.tex`, `.md`, `.txt`), get readability stats and suggestions for clearer writing, and download the report. It points things out; you decide what to change. It also manages citations and compares two documents for shared passages.

## Run locally

```bash
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
streamlit run app.py
```

## GitHub sign-in setup

1. GitHub → Settings → Developer settings → OAuth Apps → **New OAuth App**
   - Homepage URL: `http://localhost:8501`
   - Authorization callback URL: `http://localhost:8501`
2. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
3. Fill in `client_id`, `client_secret`, and your GitHub username in `allowed_users`.

Sign-in is checked on the server and kept in the server-side session only (refreshing the page signs you out). Only public profile info is requested.

## Tests

```bash
pip install pytest
python -m pytest
```

## Roadmap

1. ✅ Basic app: stats, reading ease, wordy phrases, long sentences
2. ✅ spaCy checks: passive voice, repeated words, weak verbs, filler adverbs
3. ✅ Upload `.docx` / `.tex` / `.md` / `.txt`, downloadable Markdown report, smarter sentence splitting
4. ✅ GitHub login with server-side checks and an allow-list
5. Dark theme and a hub with four pages: Writing Checker (inline highlights), Citation Inserter (DOI lookup, IEEE/APA/MLA/Harvard, BibTeX/JSON/LaTeX export), Pairwise Document Similarity (n-grams, winnowing, matching passages), Feature Request & Bug Reporter (pre-filled GitHub issues)
6. Plagiarism Checker: a draft against many sources, with each match marked as quoted/cited or not cited
7. Deploy to Streamlit Cloud
