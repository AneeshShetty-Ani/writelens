# WriteLens

**Live app: [writelens.streamlit.app](https://writelens.streamlit.app)**

A writing assistant built with Python and Streamlit. Paste text or upload a document, and WriteLens highlights what could be clearer, checks it against sources for copied passages, formats your citations, and compares two documents. It points things out; you decide what to change. Every check runs on the server with open-source libraries, so your text is never sent to an AI service, and nothing is saved.

<!-- To add a screenshot: save one as docs/screenshot.png and remove the comment marks around the next line. -->
<!-- ![WriteLens Writing Checker](docs/screenshot.png) -->

## Features

| Page | What it does |
|---|---|
| **Writing Checker** | A 0–100 writing score, reading ease, grade level, and reading / speaking time. Highlights wordy phrases, clichés, filler adverbs, contractions, mixed UK/US spelling, passive voice and long sentences in place, with a card for each saying what to do. Gives an **Improved Text** with the safe fixes applied. Report download as **PDF, Word or Markdown**. |
| **Plagiarism** | Similarity % between two texts with copied phrases highlighted, or a draft checked against many sources, with each match marked *cited* (quoted or referenced) or *not cited*. |
| **Citations** | Look up a reference by DOI (Crossref) or website URL, or enter it by hand. Formats in IEEE, APA, MLA or Harvard; replaces `[@key]` markers in your text; exports BibTeX, CSL-JSON and LaTeX. |
| **Compare** | Two documents side by side: n-gram overlap, winnowing fingerprints (the method behind Stanford's MOSS) and cosine similarity, with matching passages highlighted. |
| **Feedback** | Sends a bug report or feature request to this repo as a pre-filled GitHub issue. |
| **How it works** | Explains every check and formula in plain English. |

Uploads: `.docx`, `.pdf`, `.tex`, `.md` and `.txt`.

## How sign-in works

Sign-in uses **GitHub OAuth**. Only public profile information is requested. To use the app, star this repo and follow [@AneeshShetty-Ani](https://github.com/AneeshShetty-Ani); the sign-in screen checks both and lets you in once they're done. You then stay signed in for 7 days, even after refreshing the page, through a signed pass in the address bar that the server checks. **Logout** removes it.

## Built with

Python · Streamlit · spaCy (grammar checks) · python-docx · pypdf · fpdf2 · requests (Crossref API) · difflib · pytest

## Run it yourself

```bash
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

`requirements.txt` includes the spaCy English model, so no separate download is needed.

### GitHub sign-in setup

1. GitHub → Settings → Developer settings → OAuth Apps → **New OAuth App**
   - Homepage URL: `http://localhost:8501`
   - Authorization callback URL: `http://localhost:8501`
2. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
3. Fill in `client_id`, `client_secret` and `redirect_uri`. Then either list GitHub usernames in `allowed_users`, or set `owner`, `repo` and `require_star_follow = true` to let anyone in who stars and follows.

On Streamlit Cloud, the same settings go in **Manage app → Settings → Secrets**, with the live URL as the callback.

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
5. ✅ Dark theme and a hub: Writing Checker with inline highlights, Citations, Compare, Feedback
6. ✅ Plagiarism Checker: a draft against many sources, with each match marked as cited or not cited
7. ✅ Deployed to Streamlit Cloud, with star + follow sign-in
8. ✅ v1.4: PDF upload, PDF/Word reports, clichés, contractions, mixed UK/US spelling, reading time, stay signed in
