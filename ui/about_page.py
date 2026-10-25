import streamlit as st

from analysis import (
    ENDING_REPEAT_SHARE, LONG_SENTENCE_WORDS, READ_WPM, REPEATED_START_RUN, SECOND_PERSON_MIN, SPEAK_WPM,
    SPELLING_TERM_MIN, VARIETY_MIN_SENTENCES, VARIETY_MIN_SPREAD,
)
from modes import MODES
from score import WEIGHTS
from similarity import MATCH_WORDS, NGRAM
from structure import PARAGRAPH_MAX_WORDS, SIMILAR_PARAGRAPHS
from ai import DEFAULT_DAILY_LIMIT
from ai_tasks import PART_CHARS

# (title, icon, explanation)
SECTIONS = [
    ("Writing Checker", ":material/edit_note:", f"""
- **Wordy phrases**: a list of about 25 phrases with shorter versions (*due to the fact that → because*). The
  longest phrase is matched first so the same words are never counted twice.
- **Long sentences**: sentences over {LONG_SENTENCE_WORDS} words. Sentences are split at `. ! ?` and line breaks,
  ignoring abbreviations like *Dr.* and *e.g.*
- **Clichés, contractions and mixed UK/US spelling**: clichés come from a list of overused expressions
  (*think outside the box*). Contractions (*don't*, *it's*) are shown with their long form, since essays usually
  avoid them. Spelling looks for word patterns like *-ise/-ize*, *-our/-or* and *-re/-er*; if both kinds appear,
  the less-used one is marked so the text can be made consistent.
- **Spelling**: words are checked against an English word list with **pyspellchecker**, which works offline.
  To avoid false alarms it only checks all-lowercase words (so names and places are skipped), ignores links,
  accepts UK spellings, skips words used {SPELLING_TERM_MIN}+ times (usually your technical terms), and only
  reports a word when it finds a close correction, as typos nearly always have one.
- **Formal tone**: a list of casual words with formal choices (*gonna → going to*, *a lot of → many*), and a
  note when "you" / "your" appears {SECOND_PERSON_MIN}+ times, since essays rarely address the reader.
- **Repeated sentence starts**: {REPEATED_START_RUN}+ sentences in a row beginning with the same word.
- **Openings and conclusions**: the first paragraph is checked for openings that tell the reader nothing
  (*In today's world*, *Webster's dictionary defines*, *In this essay I will*). With 3+ paragraphs, the last one
  is flagged if {ENDING_REPEAT_SHARE:.0%}+ of its 4-word runs also appear in the first (it repeats the
  introduction), or if it has a citation or a statistic (new evidence belongs in the body).
- **Writing modes**: {" ".join(f"*{name}*: {desc}" for name, (desc, _) in MODES.items())}
- **Why?**: each card explains the rule behind it, with a before and after example.
- **Fix pasted text** joins lines broken by copying from a PDF, rejoins words split by a hyphen, and removes
  page numbers, double spaces and invisible characters.
- **Reading and speaking time**: words ÷ {READ_WPM} (average silent reading speed) and ÷ {SPEAK_WPM} (a
  comfortable pace for a talk).
- **Sentence variety**: the chart shows the words in each sentence. With {VARIETY_MIN_SENTENCES}+ sentences, if
  the standard deviation of their lengths is under {VARIETY_MIN_SPREAD:.0%} of the average, they're all about
  the same length and the writing tends to sound flat.
- **Score change between drafts**: each analysis remembers its score and issue counts (in memory, for this
  visit only). Analyse an edited version and you see the change and which issues were fixed or are new.
  **Clear All** forgets the previous draft.
- **Word limit**: enter your assignment's limit. Within 10% under it counts as on target.
- **Improved Text** also writes out contractions that have only one meaning (*don't → do not*). Ones with two
  (*it's* = it is / it has, *he'd* = he would / he had) are left for you.
- **Passive voice, weak verbs, filler adverbs, repeated words**: found with **spaCy**, an NLP library that tags
  each word's part of speech and grammar role. A sentence is passive when spaCy finds a passive subject or
  passive helper verb (`nsubjpass` / `auxpass`), as in *the report **was written***.
- **Reading ease and grade level**: the Flesch and Flesch-Kincaid formulas, which use average sentence length
  and syllables per word.
- **Writing score**: starts at 100 and loses points per 100 words for each issue
  ({", ".join(f"{k.replace('_', ' ')} −{v}" for k, v in WEIGHTS.items())}), plus a little more if the text is
  hard to read. Measuring per 100 words means a long essay isn't punished just for being long.
"""),
    ("Deeper look", ":material/insights:", f"""
- Paragraphs are split at blank lines (or line breaks, if there are none); short lines that don't end like a
  sentence are treated as headings.
- **Reverse outline**: each paragraph's first sentence (usually its main point) and its most used content words.
  Words are compared by their stem, so *study* and *studies* count as one. Two paragraphs are marked as covering
  the same ground when the cosine similarity of their word counts is {SIMILAR_PARAGRAPHS} or more. Paragraphs over
  {PARAGRAPH_MAX_WORDS} words, and one-sentence paragraphs, get a note.
- **Word budget**: words in the first paragraph, the middle ones and the last. An introduction or conclusion
  under 5% or over 20% of the text gets a note.
- **Reader effort**: each sentence scores up to 0.5 for length (full at {LONG_SENTENCE_WORDS + 10} words), up to
  0.35 for its share of 3+ syllable words (full at 30%), and 0.15 if it's passive. Under 0.35 is easy, under 0.6
  medium, the rest hard.
- **Listen** uses your browser's built-in speech (the Web Speech API) and prefers voices that run on your device.
  The text goes from this page to your browser's voice, not to the WriteLens server.
"""),
    ("Assignment Checker", ":material/assignment:", """
- **Tasks**: instruction words in the question (*compare*, *evaluate*, *discuss*, *explain*, *analyse*,
  *recommend*, *define*, *reflect*) are matched with signs in the essay: *whereas* and *unlike* for comparing,
  *however* and *limitation* for evaluating, *because* and *as a result* for explaining, and so on. Two or more
  signs count as covered, one as partly.
- **Numbers**: *three sources*, *two examples*, *five paragraphs* are counted (sources by distinct citations
  such as *(Smith, 2020)* or *[1]*, examples by *for example* / *such as*). Things that can't be counted, like
  *reasons*, are listed for you to check.
- **Length**: a word count (within 10%) or a range such as *1,200–1,500 words*.
- **Structure**: an introduction and conclusion (3+ paragraphs, the last one summing up) and a *References* heading
  if a reference list is asked for.
- **Topics**: the question's key words (not the instruction words), found by stem, with the paragraphs they
  appear in.
- **Improved version**: your essay with the Writing Checker's safe fixes applied, and a **[TO DO: ...]** note at
  each place that still needs your work: missing tasks and topics at the end of the main body, an introduction
  at the start, a conclusion at the end, and a References heading if one was asked for. WriteLens doesn't write
  the missing content for you; the notes show where your own words are needed.
- It matches words, not meaning, so treat it as a checklist rather than a mark.
"""),
    ("AI engine (hybrid)", ":material/auto_awesome:", f"""
- Every tool works **offline**, with the open-source checks described here. When the app owner has added a free
  AI key, every tool also uses **AI automatically**, on top of the offline results. If the AI is busy or fails,
  the tool says so and shows the offline results alone.
- **Whole texts**: a long text is read in parts of about {PART_CHARS:,} characters (cut at paragraph breaks),
  sent side by side and put back together, so the AI covers all of it. One check counts once towards the
  daily limit, however many parts it has. A part the AI couldn't check keeps its offline results.
- **Writing**: the AI looks for problems rules can't see (grammar agreement, unclear sentences, weak logic) and
  polishes the Improved Text, keeping your meaning.
- **Assignment**: the AI judges tasks, topics and structure by meaning and gives a specific hint for each gap.
  Word counts and citations are still counted exactly. It says what to add; it doesn't write it for you.
- **Plagiarism** and **Compare**: the AI looks for passages reworded from a source, which word matching can't catch.
- **Citations**: paste a reference written any way. A DOI, ISBN or web address is looked up directly; otherwise the
  AI reads the fields and Crossref is searched to confirm the work exists. Offline, a reference in a standard
  style (APA, MLA, Harvard, Chicago, IEEE) is read from its punctuation. For a website that hides its author or
  date, the AI looks for them in the page's text.
- **Feedback**: the AI tidies your report into a clear GitHub issue (title, spelling, headings), adding nothing;
  you can still send your own wording. Your contact details are never sent to the AI.
- **Checked answers**: every quote the AI gives must really be in your text (and in the source, for
  plagiarism), a rewrite must stay about the same length, and a reference title must come from what you typed.
  Anything else is thrown away, and a reply that fails goes to the next model.
- **Free models in a chain**: OpenRouter gives one key for many free models. WriteLens reads which ones are on
  offer, tries them in turn, skips ones that refuse, and tries the last one that worked first. Google Gemini and
  Groq keys can be added as backups. Each AI result says which model produced it.
- **Status light** (under your name): green blinking = online; yellow, slow = maintenance (models busy, or your
  {DEFAULT_DAILY_LIMIT} AI checks for today are used up); red, fast = stopped (key refused or repeated failures);
  grey = offline (no AI set up).
- Your text is sent to the AI provider only when you press a check button, and the same text isn't sent twice.
  Free models may keep what they're sent, so leave out personal details. AI can be wrong; follow your course's
  rules on using AI.
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
- **Book (ISBN)** checks the ISBN's check digit, then asks Open Library (a free book catalogue) for the title,
  authors, publisher and year.
- References are formatted in **IEEE, APA, MLA, Harvard or Chicago** (author-date) style.
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
- You stay signed in for 7 days, even after refreshing the page: the address bar holds a signed pass
  (`?session=...`) that the server checks and that can't be forged. **Logout** removes it. Don't share the full
  address while signed in, since it carries that pass.
- Your text is processed in memory and is not saved anywhere. The only time it leaves the WriteLens server is
  when the AI engine is set up and you run a check (see above).
"""),
    ("Uploads and reports", ":material/upload_file:", """
- Upload **.docx, .pdf, .tex, .md or .txt**. PDF text is read with **pypdf**; a scanned PDF (a picture of pages)
  has no text to read.
- Download the Writing Checker report as **PDF** (made with **fpdf2**, using the free DejaVu Sans font so
  accented letters, Greek and Cyrillic print correctly), **Word** (python-docx) or **Markdown**.
"""),
]


def render() -> None:
    st.markdown("### :material/help: How it works")
    st.write("Every check runs on the server with open-source Python and works offline. When an AI key is set up, "
             "every tool also uses free AI models automatically (see AI engine below).")
    for title, icon, body in SECTIONS:
        with st.expander(f"{icon} **{title}**", expanded=title == "Writing Checker"):
            st.markdown(body)
    st.caption("Built with Python, Streamlit, spaCy, pyspellchecker, difflib, requests (Crossref and Open Library "
               "APIs), python-docx, pypdf, fpdf2 and the Web Speech API. Every update is tested automatically on "
               "GitHub Actions.")
