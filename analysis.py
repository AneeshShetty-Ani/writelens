"""Plain-Python text analysis: basic stats, readability, and wordy-phrase hints."""

import re
from dataclasses import dataclass, field

# Split after . ! ? followed by whitespace, or at line breaks (headings, list items).
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
WORD = re.compile(r"[A-Za-z']+")
# Abbreviations whose dot does not end a sentence. "etc." is left out since it often does.
ABBREVIATIONS = ("Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Sr.", "Jr.", "St.", "vs.", "e.g.", "i.e.", "Fig.", "No.", "al.")
PLACEHOLDER = "\x00"

# Wordy phrase -> plainer suggestion. The writer decides whether to change it.
WORDY_PHRASES = {
    # Matches "it is (very) important to note that" too.
    "important to note": "(often can be cut)",
    "it should be noted that": "(often can be cut)",
    "it can be said that": "(often can be cut)",
    "in conclusion": "(often can be cut)",
    "needless to say": "(often can be cut)",
    "at the end of the day": "ultimately",
    "the fact that": "that",
    "over the course of": "during / over",
    "due to the fact that": "because",
    "in spite of the fact that": "although",
    "a number of": "some / several",
    "prior to": "before",
    "in terms of": "in / for",
    "each and every": "each / every",
    "first and foremost": "first",
    "in the near future": "soon",
    "in order to": "to",
    "at this point in time": "now",
    "a large number of": "many",
    "has the ability to": "can",
    "in the event that": "if",
    "for the purpose of": "for / to",
    "with regard to": "about",
    "is able to": "can",
}

LONG_SENTENCE_WORDS = 30


@dataclass
class Report:
    words: int = 0
    sentences: int = 0
    avg_sentence_len: float = 0.0
    reading_ease: float = 0.0
    grade_level: float = 0.0
    long_sentences: list[str] = field(default_factory=list)
    wordy: list[tuple[str, str, int]] = field(default_factory=list)


def grade_label(grade: float) -> str:
    if grade < 6:
        return "Very easy"
    if grade < 9:
        return "Middle school"
    if grade < 13:
        return "High school"
    if grade < 17:
        return "College"
    return "Graduate"


def count_syllables(word: str) -> int:
    word = word.lower().strip("'")
    if not word:
        return 0
    groups = re.findall(r"[aeiouy]+", word)
    count = len(groups)
    if word.endswith("e") and count > 1 and not word.endswith("le"):
        count -= 1
    return max(count, 1)


def split_sentences(text: str) -> list[str]:
    protected = text.strip()
    for abbr in ABBREVIATIONS:
        protected = re.sub(rf"\b{re.escape(abbr)}", abbr.replace(".", PLACEHOLDER), protected)
    parts = SENTENCE_SPLIT.split(protected)
    return [s.replace(PLACEHOLDER, ".").strip() for s in parts if s.strip()]


def analyze(text: str) -> Report:
    report = Report()
    sentences = split_sentences(text)
    words = WORD.findall(text)
    if not sentences or not words:
        return report

    report.words = len(words)
    report.sentences = len(sentences)
    report.avg_sentence_len = len(words) / len(sentences)

    syllables = sum(count_syllables(w) for w in words)
    # Flesch Reading Ease: higher = easier (60-70 is plain English).
    report.reading_ease = (
        206.835 - 1.015 * report.avg_sentence_len - 84.6 * (syllables / len(words))
    )
    # Flesch-Kincaid grade: the US school year that can follow the text.
    report.grade_level = max(0.0, 0.39 * report.avg_sentence_len + 11.8 * (syllables / len(words)) - 15.59)

    report.long_sentences = [
        s for s in sentences if len(WORD.findall(s)) > LONG_SENTENCE_WORDS
    ]

    # Longest phrases first, blanking each match, so "due to the fact that" is not
    # also reported as "the fact that".
    remaining = text
    for phrase in sorted(WORDY_PHRASES, key=len, reverse=True):
        remaining, hits = re.subn(rf"\b{re.escape(phrase)}\b", PLACEHOLDER, remaining, flags=re.IGNORECASE)
        if hits:
            report.wordy.append((phrase, WORDY_PHRASES[phrase], hits))

    return report
