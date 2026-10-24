"""Plain-Python text analysis: basic stats, readability, and wordy-phrase hints."""

import re
from dataclasses import dataclass, field
from functools import lru_cache

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
# Sentence variety: with at least this many sentences, lengths whose standard deviation is under
# this share of the average count as "all about the same length".
VARIETY_MIN_SENTENCES = 5
VARIETY_MIN_SPREAD = 0.25

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
# Casual words and phrases -> a more formal choice, for essays and reports.
INFORMAL = {
    "gonna": "going to", "wanna": "want to", "gotta": "have to", "kinda": "somewhat", "sorta": "somewhat",
    "a lot of": "many / much", "lots of": "many / much", "tons of": "many / much", "loads of": "many / much",
    "stuff": "a specific word (material, items...)", "kids": "children", "guys": "people",
    "awesome": "excellent", "okay": "acceptable", "ok": "acceptable", "anyways": "anyway",
    "pretty much": "almost", "get rid of": "remove", "figure out": "determine", "come up with": "develop / propose",
    "big deal": "significant", "nowadays": "today / currently", "freaking": "(cut it)",
}
INFORMAL_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in sorted(INFORMAL, key=len, reverse=True)) + r")\b", re.IGNORECASE)
SECOND_PERSON = re.compile(r"\byou(?:r|rs|rself|rselves)?\b", re.IGNORECASE)
SECOND_PERSON_MIN = 3  # one "you" in a quote is fine; several means the essay is talking to the reader

# Sentence starts: this many sentences in a row beginning with the same word reads repetitively.
REPEATED_START_RUN = 3

# Spelling: only all-lowercase words are checked, so names, places and acronyms are never flagged.
# A word used this often is probably a technical term the dictionary doesn't know.
SPELLING_TERM_MIN = 3
SPELLING_MAX = 50  # distinct misspellings to suggest fixes for, so a huge document stays fast
CHECKABLE_WORD = re.compile(r"(?<![\w'’-])[a-z]+(?![\w'’-])")
LINK = re.compile(r"\S+@\S+|https?://\S+|www\.\S+")
# Correct words the dictionary doesn't know: newer words, and UK spellings the UK/US patterns don't cover.
KNOWN_WORDS = {
    "dataset", "datasets", "covid", "email", "emails", "online", "offline", "app", "apps", "smartphone", "smartphones",
    "website", "websites", "blog", "blogs", "wifi", "login", "username", "chatbot", "chatbots", "cybersecurity",
    "programme", "programmes", "cheque", "cheques", "tyre", "tyres", "aluminium", "mould", "practise", "practised",
    "licence", "licences", "ageing", "jewellery", "enrol", "enrolment", "fulfil", "fulfilment", "judgement",
    "towards", "whilst", "amongst", "learnt", "spelt", "dreamt", "burnt", "favour", "favours", "colours", "metres",
    "kilometres", "manoeuvre", "paediatric", "anaemia", "oestrogen", "sceptical", "storey", "draught", "plough",
}


@lru_cache(maxsize=1)
def spellchecker():
    from spellchecker import SpellChecker

    return SpellChecker()


def find_misspellings(text: str) -> list[tuple[str, str, int]]:
    """(word, suggested fix, count) for each probable misspelling, most frequent first."""
    text = LINK.sub(" ", text)
    counts: dict[str, int] = {}
    for m in CHECKABLE_WORD.finditer(text):
        counts[m.group()] = counts.get(m.group(), 0) + 1
    candidates = [w for w, n in counts.items() if n < SPELLING_TERM_MIN and w not in KNOWN_WORDS
                  and not UK_SPELLING.fullmatch(w) and not US_SPELLING.fullmatch(w)]
    checker = spellchecker()
    unknown = [w for w in checker.unknown(candidates) if not checker.known(us_forms(w))]
    found = []
    for word in sorted(unknown, key=lambda w: (-counts[w], w))[:SPELLING_MAX]:
        fix = checker.correction(word)
        # a typo nearly always has a close correction; a word without one is usually a technical term
        if fix and fix != word:
            found.append((word, fix, counts[word]))
    return found


# UK spelling -> US spelling, for words the UK/US patterns don't list ("organisers", "urbanisation")
UK_TO_US = [("is", "iz"), ("our", "or"), ("tre", "ter"), ("yse", "yze"), ("ll", "l"), ("ogue", "og"), ("ence", "ense")]


def us_forms(word: str) -> list[str]:
    return [word.replace(uk, us) for uk, us in UK_TO_US if uk in word]


def repeated_start_runs(sentences: list[str]) -> list[tuple[str, int, int]]:
    """(first word, index of the first sentence, number of sentences) for each run of
    REPEATED_START_RUN+ sentences in a row that begin with the same word."""
    firsts = [(WORD.findall(s) or [""])[0].lower() for s in sentences]
    runs, i = [], 0
    while i < len(firsts):
        j = i
        while j + 1 < len(firsts) and firsts[j + 1] == firsts[i]:
            j += 1
        if firsts[i] and j - i + 1 >= REPEATED_START_RUN:
            runs.append((firsts[i], i, j - i + 1))
        i = j + 1
    return runs


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
    sentence_lengths: list[int] = field(default_factory=list)  # words in each sentence, in order
    wordy: list[tuple[str, str, int]] = field(default_factory=list)
    cliches: list[tuple[str, int]] = field(default_factory=list)
    contractions: list[tuple[str, int]] = field(default_factory=list)
    misspellings: list[tuple[str, str, int]] = field(default_factory=list)  # (word, fix, count)
    informal: list[tuple[str, str, int]] = field(default_factory=list)  # (phrase, formal choice, count)
    second_person: int = 0  # uses of "you" / "your", when there are SECOND_PERSON_MIN or more
    repeated_starts: list[tuple[str, int, int]] = field(default_factory=list)  # see repeated_start_runs()
    # filled only when the text mixes the two: the UK-spelled and US-spelled words, with counts
    uk_spelling: list[tuple[str, int]] = field(default_factory=list)
    us_spelling: list[tuple[str, int]] = field(default_factory=list)

    @property
    def monotonous(self) -> bool:
        """True when most sentences have nearly the same length, which makes writing read flat."""
        lengths = self.sentence_lengths
        if len(lengths) < VARIETY_MIN_SENTENCES:
            return False
        mean = sum(lengths) / len(lengths)
        spread = (sum((n - mean) ** 2 for n in lengths) / len(lengths)) ** 0.5
        return spread / mean < VARIETY_MIN_SPREAD

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

    report.sentence_lengths = [len(WORD.findall(s)) for s in sentences]
    report.long_sentences = [
        s for s, n in zip(sentences, report.sentence_lengths) if n > LONG_SENTENCE_WORDS
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
    report.misspellings = find_misspellings(text)
    report.informal = [(p, INFORMAL[p], n) for p, n in count_matches(INFORMAL_PATTERN, text)]
    you = len(SECOND_PERSON.findall(text))
    report.second_person = you if you >= SECOND_PERSON_MIN else 0
    report.repeated_starts = repeated_start_runs(sentences)
    uk, us = count_matches(UK_SPELLING, text), count_matches(US_SPELLING, text)
    if uk and us:
        report.uk_spelling, report.us_spelling = uk, us

    return report
