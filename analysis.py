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
READ_WPM = 238  # average silent reading speed for adults
SPEAK_WPM = 130  # a comfortable pace for a speech or presentation

# Overused expressions. "at the end of the day" is a wordy phrase above, so it isn't repeated here.
CLICHES = (
    "think outside the box", "last but not least", "in this day and age", "only time will tell",
    "avoid like the plague", "a piece of cake", "the tip of the iceberg", "easier said than done",
    "at the drop of a hat", "better late than never", "hit the nail on the head", "few and far between",
    "in the nick of time", "every cloud has a silver lining", "a blessing in disguise", "since the dawn of time",
    "all walks of life", "it goes without saying", "when all is said and done", "a double-edged sword",
    "the calm before the storm", "a level playing field", "the elephant in the room", "the bigger picture",
    "par for the course", "food for thought", "a game changer", "push the envelope",
)

# Contractions, which are fine in casual writing but usually avoided in essays and reports.
# 's only after these words, since "Sam's" is a possessive, not a contraction.
CONTRACTION = re.compile(
    r"\b(?:[A-Za-z]+n['’]t|[A-Za-z]+['’](?:re|ve|ll|m|d)|(?:it|that|there|what|he|she|who|here|where|let)['’]s)\b",
    re.IGNORECASE,
)
CONTRACTION_SPECIAL = {"can't": "cannot", "won't": "will not", "shan't": "shall not", "ain't": "is not",
                       "let's": "let us", "i'm": "I am", "i've": "I have", "i'll": "I will", "i'd": "I would / had"}
CONTRACTION_ENDINGS = {"n't": " not", "'re": " are", "'ve": " have", "'ll": " will", "'m": " am",
                       "'d": " would / had", "'s": " is / has"}

# UK spelling pattern, US spelling pattern. A text should stick to one of the two.
_ISE_STEMS = ("organ", "real", "recogn", "emphas", "summar", "apolog", "critic", "priorit", "minim", "maxim",
              "optim", "util", "special", "categor", "standard", "character", "visual", "normal", "final",
              "author", "civil", "modern", "memor", "global")
_OUR_STEMS = ("colo", "favo", "behavio", "hono", "labo", "neighbo", "humo", "flavo", "harbo", "rumo", "vigo", "endeavo")
_LL_STEMS = ("travel", "model", "label", "cancel", "signal", "level", "fuel", "marvel")
SPELLING = [
    (rf"(?:{'|'.join(_ISE_STEMS)})is(?:e|es|ed|ing|ation|ations)", rf"(?:{'|'.join(_ISE_STEMS)})iz(?:e|es|ed|ing|ation|ations)"),
    # not "analyses", which is also the US plural of "analysis"
    (r"(?:analy|paraly)s(?:e|ed|ing|er|ers)", r"(?:analy|paraly)z(?:e|ed|ing|er|ers)"),
    (rf"(?:{'|'.join(_OUR_STEMS)})ur(?:|s|ed|ing|ful|ite|ites|able|al|hood|hoods|less)",
     rf"(?:{'|'.join(_OUR_STEMS)})r(?:|s|ed|ing|ful|ite|ites|able|al|hood|hoods|less)"),
    (r"(?:cent|theat|fib|lit)re(?:s|d)?", r"(?:cent|theat|fib|lit)er(?:s|ed)?"),
    (r"(?:defen|offen|preten)ce", r"(?:defen|offen|preten)se"),
    (rf"(?:{'|'.join(_LL_STEMS)})l(?:ed|ing|er|ers)", rf"(?:{'|'.join(_LL_STEMS)})(?:ed|ing|er|ers)"),
    (r"grey(?:s|er|est|ish)?|catalogue(?:s|d)?", r"gray(?:s|er|est|ish)?|catalog(?:s|ed)?"),
]
CLICHE_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(c) for c in CLICHES) + r")\b", re.IGNORECASE)
UK_SPELLING = re.compile(r"\b(?:" + "|".join(uk for uk, _ in SPELLING) + r")\b", re.IGNORECASE)
US_SPELLING = re.compile(r"\b(?:" + "|".join(us for _, us in SPELLING) + r")\b", re.IGNORECASE)


@dataclass
class Report:
    words: int = 0
    sentences: int = 0
    avg_sentence_len: float = 0.0
    reading_ease: float = 0.0
    grade_level: float = 0.0
    long_sentences: list[str] = field(default_factory=list)
    wordy: list[tuple[str, str, int]] = field(default_factory=list)
    cliches: list[tuple[str, int]] = field(default_factory=list)
    contractions: list[tuple[str, int]] = field(default_factory=list)
    # filled only when the text mixes the two: the UK-spelled and US-spelled words, with counts
    uk_spelling: list[tuple[str, int]] = field(default_factory=list)
    us_spelling: list[tuple[str, int]] = field(default_factory=list)

    @property
    def minority_spelling(self) -> list[tuple[str, int]]:
        """The less-used of the two spellings: the words to change so the text is consistent."""
        uk, us = (sum(n for _, n in words) for words in (self.uk_spelling, self.us_spelling))
        return self.us_spelling if us < uk else self.uk_spelling


def duration(words: int, wpm: int) -> str:
    minutes = words / wpm
    return "under 1 min" if minutes < 1 else f"{round(minutes)} min"


def expand_contraction(word: str) -> str:
    """The long form of a contraction, e.g. "don't" -> "do not"."""
    lower = word.lower().replace("’", "'")
    if lower in CONTRACTION_SPECIAL:
        return CONTRACTION_SPECIAL[lower]
    for ending, full in CONTRACTION_ENDINGS.items():
        if lower.endswith(ending):
            return lower[: -len(ending)] + full
    return lower


def count_matches(pattern: re.Pattern, text: str) -> list[tuple[str, int]]:
    """Each distinct match (lower-cased, straight apostrophes) with how often it occurs, most frequent first."""
    counts: dict[str, int] = {}
    for m in pattern.finditer(text):
        word = m.group().lower().replace("’", "'")
        counts[word] = counts.get(word, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


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

    report.cliches = count_matches(CLICHE_PATTERN, text)
    report.contractions = count_matches(CONTRACTION, text)
    uk, us = count_matches(UK_SPELLING, text), count_matches(US_SPELLING, text)
    if uk and us:
        report.uk_spelling, report.us_spelling = uk, us

    return report
