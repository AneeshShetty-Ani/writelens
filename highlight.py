"""Find character spans of writing issues and render text with them highlighted."""

import html
import re

from analysis import (
    CHECKABLE_WORD, CLICHE_PATTERN, CONTRACTION, INFORMAL_PATTERN, LINK, LONG_SENTENCE_WORDS, SECOND_PERSON,
    UK_SPELLING, US_SPELLING, WORD, WORDY_PHRASES, Report, analyze, split_sentences,
)
from nlp_checks import is_filler_adverb, is_passive, load_nlp

# category -> label shown in the legend and tooltips
LABELS = {
    "typo": "Spelling mistake",
    "wordy": "Wordy phrase",
    "informal": "Informal",
    "starts": "Repeated sentence start",
    "cliche": "Cliché",
    "contraction": "Contraction",
    "spelling": "Mixed UK/US spelling",
    "adverb": "Filler adverb",
    "passive": "Passive voice",
    "long": f"Long sentence (over {LONG_SENTENCE_WORDS} words)",
    "match": "Matching passage",
    "uncited": "Matching passage, not cited",
    "cited": "Matching passage, quoted or cited",
}

Span = tuple[int, int, str]


def find_spans(text: str, report: Report | None = None) -> list[Span]:
    """Spans of every issue. Pass the text's analyze() result to avoid running the spellchecker twice."""
    report = report or analyze(text)
    spans: list[Span] = []

    typos = {word for word, _, _ in report.misspellings}
    if typos:
        unlinked = LINK.sub(lambda m: " " * len(m.group()), text)  # same offsets, links blanked out
        spans.extend((m.start(), m.end(), "typo") for m in CHECKABLE_WORD.finditer(unlinked) if m.group() in typos)
    spans.extend((m.start(), m.end(), "informal") for m in INFORMAL_PATTERN.finditer(text))
    if report.second_person:
        spans.extend((m.start(), m.end(), "informal") for m in SECOND_PERSON.finditer(text))

    # Longest phrases first; blank each match (keeping offsets) so overlaps count once.
    remaining = text
    for phrase in sorted(WORDY_PHRASES, key=len, reverse=True):
        pattern = rf"\b{re.escape(phrase)}\b"
        for m in re.finditer(pattern, remaining, re.IGNORECASE):
            spans.append((m.start(), m.end(), "wordy"))
        remaining = re.sub(pattern, lambda m: " " * len(m.group()), remaining, flags=re.IGNORECASE)

    spans.extend((m.start(), m.end(), "cliche") for m in CLICHE_PATTERN.finditer(text))
    spans.extend((m.start(), m.end(), "contraction") for m in CONTRACTION.finditer(text))
    # with mixed spelling, mark the less-used form: those are the words to change
    uk, us = list(UK_SPELLING.finditer(text)), list(US_SPELLING.finditer(text))
    if uk and us:
        spans.extend((m.start(), m.end(), "spelling") for m in (us if len(us) < len(uk) else uk))

    in_run = {i for _, first, length in report.repeated_starts for i in range(first, first + length)}
    pos = 0
    for i, sentence in enumerate(split_sentences(text)):
        start = text.find(sentence, pos)
        if start < 0:
            continue
        pos = start + len(sentence)
        if len(WORD.findall(sentence)) > LONG_SENTENCE_WORDS:
            spans.append((start, pos, "long"))
        if i in in_run and (first_word := WORD.search(sentence)):
            spans.append((start + first_word.start(), start + first_word.end(), "starts"))

    nlp = load_nlp()
    if nlp is not None:
        doc = nlp(text)
        spans.extend((s.start_char, s.end_char, "passive") for s in doc.sents if is_passive(s))
        spans.extend((t.idx, t.idx + len(t), "adverb") for t in doc if is_filler_adverb(t))

    return spans


def render_html(text: str, spans: list[Span]) -> str:
    """Escape the text and wrap each run of characters in the classes of the spans covering it."""
    cuts = sorted({0, len(text), *(s for s, _, _ in spans), *(e for _, e, _ in spans)})
    parts = []
    for a, b in zip(cuts, cuts[1:]):
        chunk = html.escape(text[a:b]).replace("\n", "<br>")
        cats = sorted({c for s, e, c in spans if s <= a and e >= b})
        if cats:
            title = html.escape(", ".join(LABELS[c] for c in cats))
            classes = " ".join(f"uf-{c}" for c in cats)
            parts.append(f'<span class="{classes}" title="{title}">{chunk}</span>')
        else:
            parts.append(chunk)
    return f'<div class="uf-highlight">{"".join(parts)}</div>'


def legend_html(categories: list[str]) -> str:
    items = "".join(f'<span class="uf-{c}">{html.escape(LABELS[c])}</span>' for c in categories)
    return f'<div class="uf-legend">{items}</div>'
