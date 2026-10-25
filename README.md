# WriteLens

[![Tests](https://github.com/AneeshShetty-Ani/writelens/actions/workflows/tests.yml/badge.svg)](https://github.com/AneeshShetty-Ani/writelens/actions/workflows/tests.yml)

**Live app: [writelens.streamlit.app](https://writelens.streamlit.app)**

A writing assistant built with Python and Streamlit. Paste text or upload a document, and WriteLens highlights what could be clearer, checks it against sources for copied passages, formats your citations, and compares two documents. It points things out; you decide what to change. Every check runs on the server with open-source libraries, so your text is never sent to an AI service, and nothing is saved.
## Features

| Page | What it does |
|---|---|
| **Writing Checker** | A 0–100 writing score, reading ease, grade level, and reading / speaking time. Highlights spelling mistakes, weak openings, wordy phrases, clichés, informal words, filler adverbs, contractions, mixed UK/US spelling, repeated sentence starts, passive voice and long sentences in place, with a card for each saying what to do and a **"Why?"** lesson with a before and after. Flags conclusions that repeat the introduction or add new evidence. **Writing modes** (Essay, Report, Email, Casual) switch off checks that don't fit. A **Deeper look** shows a reverse outline of your paragraphs, a word budget (intro / body / conclusion), a reader effort map, and reads your text aloud. Re-analyse an edited draft to see the **score change and which issues you fixed**; set a **word limit** to track length; **fix pasted text** from PDFs in one click. Gives an **Improved Text** with the safe fixes applied. Report download as **PDF, Word or Markdown**. |
| **Assignment** | Paste the assignment question and your essay: lists what the question asks for (tasks like *compare* or *evaluate*, the number of sources and examples, the word count, structure and key topics) and marks each one covered, partly covered or missing. Ends with an **improved version** of your essay: the safe fixes applied and a `[TO DO]` note wherever something is still missing. |
| **AI engine** *(hybrid)* | Every tool works offline. With a free AI key set up, Writing (AI review + polished Improved Text), Assignment (requirements judged by meaning), Plagiarism (reworded passages) and Citations (paste a reference written any way) also use AI automatically, falling back to offline when it's busy. Free models are tried in a chain, every AI answer is checked against your text, and a status light under your name shows Online / Maintenance / Stopped / Offline. |
| **Plagiarism** | Similarity % between two texts with copied phrases highlighted, or a draft checked against many sources, with each match marked *cited* (quoted or referenced) or *not cited*. |
| **Citations** | Look up a reference by DOI (Crossref), book ISBN (Open Library) or website URL, or enter it by hand. Formats in IEEE, APA, MLA, Harvard or Chicago; replaces `[@key]` markers in your text; exports BibTeX, CSL-JSON and LaTeX. |
| **Compare** | Two documents side by side: n-gram overlap, winnowing fingerprints (the method behind Stanford's MOSS) and cosine similarity, with matching passages highlighted. |
| **Feedback** | Sends a bug report or feature request to this repo as a pre-filled GitHub issue. |
| **How it works** | Explains every check and formula in plain English. |

Uploads: `.docx`, `.pdf`, `.tex`, `.md` and `.txt`.

## How sign-in works

Sign-in uses **GitHub OAuth**. Only public profile information is requested. To use the app, star this repo and follow [@AneeshShetty-Ani](https://github.com/AneeshShetty-Ani); the sign-in screen checks both and lets you in once they're done. You then stay signed in for 7 days, even after refreshing the page, through a signed pass in the address bar that the server checks. **Logout** removes it.

## Built with

Python · Streamlit · spaCy (grammar checks) · pyspellchecker · Altair (charts) · python-docx · pypdf · fpdf2 with DejaVu Sans · requests (Crossref and Open Library APIs) · Web Speech API (read aloud) · OpenRouter / Gemini / Groq free models (optional AI engine) · difflib · pytest

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

### AI engine setup (optional)

Create a free key at [openrouter.ai](https://openrouter.ai) (Keys → Create key, no credit limit needed) and add it under `[ai]` in the secrets as `openrouter_key` (see `.streamlit/secrets.toml.example`). In OpenRouter's **Settings → Privacy**, turn on *Allow free endpoints that train on request data*, or most free models refuse requests. Free Gemini (`gemini_key`) and Groq (`groq_key`) keys can be added as backups. Without any key every tool runs offline and the status light is grey.

## Tests

```bash
pip install pytest
python -m pytest
```

GitHub Actions runs the full suite on every push (see the badge at the top).

## Roadmap

1. ✅ Basic app: stats, reading ease, wordy phrases, long sentences
2. ✅ spaCy checks: passive voice, repeated words, weak verbs, filler adverbs
3. ✅ Upload `.docx` / `.tex` / `.md` / `.txt`, downloadable Markdown report, smarter sentence splitting
4. ✅ GitHub login with server-side checks and an allow-list
5. ✅ Dark theme and a hub: Writing Checker with inline highlights, Citations, Compare, Feedback
6. ✅ Plagiarism Checker: a draft against many sources, with each match marked as cited or not cited
7. ✅ Deployed to Streamlit Cloud, with star + follow sign-in
8. ✅ v1.4: PDF upload, PDF/Word reports, clichés, contractions, mixed UK/US spelling, reading time, stay signed in, draft score tracking, word limit, sentence-length chart, Chicago style
9. ✅ v1.5: spelling mistakes, formal tone, repeated sentence starts, automatic tests on GitHub Actions
10. ✅ v1.6: Assignment Checker with an improved version, writing modes, reverse outline, word budget, reader effort map, read aloud, weak openings and conclusions, "Why?" lessons, fix pasted text, book citations by ISBN
11. ✅ v1.7: hybrid AI engine on free models (OpenRouter, with Gemini and Groq as backups) inside Writing, Assignment, Plagiarism and Citations, offline fallback, status light, a daily AI limit per user
