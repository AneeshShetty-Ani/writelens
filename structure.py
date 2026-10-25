"""The shape of a whole text: a reverse outline (what each paragraph is about), how the words are
split between introduction, body and conclusion, and how much effort each sentence asks of the reader."""

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from analysis import (
    LONG_SENTENCE_WORDS, WORD, count_syllables, paragraph_spans, sentence_spans, split_sentences,
)

STOPWORDS = set("""
a about above after again against all also although am an and any are as at be because been before being
below between both but by can could did do does doing down during each either else even ever every few for
from further had has have having he her here hers herself him himself his how however i if in into is it its
itself just least less let like made make many may me might more most much must my myself neither no nor not
now of off often on once one only or other others our ours ourselves out over own per perhaps quite rather
really same say says said shall she should since so some such than that the their theirs them themselves then
there these they thing things this those though through thus to too under until up upon us use used using very
was we well were what when where whether which while who whom whose why will with within without would yet you
your yours yourself yourselves also another way ways get gets got make makes many much new first second third
today essay
""".split())
# endings removed so "studies" / "study" and "changes" / "change" count as one word; the first match wins
SUFFIXES = ("ational", "ations", "ation", "ions", "ion", "ness", "ments", "ment", "ings", "ing", "ies", "ied",
            "ers", "er", "es", "ed", "ly", "s", "e")
STEM_MIN = 3  # letters that must remain
POSSESSIVE = re.compile(r"'s?$|^'")

PARAGRAPH_MAX_WORDS = 200
SIMILAR_PARAGRAPHS = 0.5  # cosine similarity of key-word counts above which two paragraphs overlap
SIMILAR_MIN_WORDS = 15  # content words each paragraph needs before it is compared
KEY_WORDS = 3
MAIN_POINT_CHARS = 160

# share of all words; outside these the intro or conclusion is out of proportion
INTRO_RANGE = (0.05, 0.2)
CONCLUSION_RANGE = (0.05, 0.2)

# reader effort: sentence length counts most, then long words, then the passive voice
EFFORT_LEVELS = ((0.35, "easy"), (0.6, "medium"), (math.inf, "hard"))
HARD_WORD_SYLLABLES = 3
EFFORT_MIN_WORDS = 3  # shorter lines are headings or fragments, not sentences to judge


def stem(word: str) -> str:
    word = word.lower()
    for suffix in SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= STEM_MIN:
            return word[: -len(suffix)] + ("y" if suffix in ("ies", "ied") else "")
    return word


def content_words(text: str) -> list[str]:
    """Words that carry meaning, without possessive endings: no stopwords, nothing shorter than 3 letters."""
    words = (POSSESSIVE.sub("", w.lower()) for w in WORD.findall(text))
    return [w for w in words if len(w) >= 3 and w not in STOPWORDS]


def key_words(text: str, n: int = KEY_WORDS) -> list[str]:
    """The most used content words, one form per stem (the first one written). When nothing repeats,
    the longest words, which tend to be the most specific."""
    counts: Counter = Counter()
    shown: dict[str, str] = {}
    for word in content_words(text):
        s = stem(word)
        counts[s] += 1
        shown.setdefault(s, word)
    ranked = sorted(counts, key=lambda s: -counts[s])  # sorted() is stable, so ties keep their first use
    repeated = [shown[s] for s in ranked[:n] if counts[s] > 1]
    return repeated or sorted(shown.values(), key=len, reverse=True)[:2]


def cosine(a: Counter, b: Counter) -> float:
    dot = sum(n * b[w] for w, n in a.items())
    norm = math.sqrt(sum(n * n for n in a.values())) * math.sqrt(sum(n * n for n in b.values()))
    return dot / norm if norm else 0.0


@dataclass
class OutlinePoint:
    number: int
    words: int
    sentences: int
    main_point: str  # the first sentence, usually the topic sentence
    key_words: list[str]
    notes: list[str] = field(default_factory=list)


def outline(text: str) -> list[OutlinePoint]:
    paragraphs = [text[s:e] for s, e in paragraph_spans(text)]
    points = []
    for i, para in enumerate(paragraphs, 1):
        sentences = split_sentences(para)
        first = " ".join((sentences[0] if sentences else para).split())
        if len(first) > MAIN_POINT_CHARS:
            first = first[: MAIN_POINT_CHARS - 3].rsplit(" ", 1)[0] + "..."
        point = OutlinePoint(i, len(WORD.findall(para)), len(sentences), first, key_words(para))
        if len(paragraphs) > 1 and len(sentences) == 1:
            point.notes.append("only one sentence: develop the idea or merge it with a neighbour")
        if point.words > PARAGRAPH_MAX_WORDS:
            point.notes.append(f"long ({point.words} words): look for a place to split it")
        points.append(point)

    stems = [Counter(stem(w) for w in content_words(p)) for p in paragraphs]
    for i, j in similar_pairs(stems):
        points[i].notes.append(f"covers much the same as paragraph {j + 1}: merge them or make the difference clear")
        points[j].notes.append(f"covers much the same as paragraph {i + 1}")
    return points


def similar_pairs(stems: list[Counter]) -> list[tuple[int, int]]:
    long_enough = [i for i, c in enumerate(stems) if sum(c.values()) >= SIMILAR_MIN_WORDS]
    return [(i, j) for n, i in enumerate(long_enough) for j in long_enough[n + 1:]
            if cosine(stems[i], stems[j]) >= SIMILAR_PARAGRAPHS]


@dataclass
class Budget:
    intro: int
    body: int
    conclusion: int
    advice: list[str]

    @property
    def total(self) -> int:
        return self.intro + self.body + self.conclusion


def word_budget(text: str) -> Budget | None:
    """Words in the first paragraph, the middle ones and the last, for texts with 3+ paragraphs."""
    counts = [len(WORD.findall(text[s:e])) for s, e in paragraph_spans(text)]
    if len(counts) < 3 or not all(counts):
        return None
    total = sum(counts)
    budget = Budget(counts[0], sum(counts[1:-1]), counts[-1], [])
    for name, words, (low, high) in (("introduction", budget.intro, INTRO_RANGE),
                                     ("conclusion", budget.conclusion, CONCLUSION_RANGE)):
        share = words / total
        if share > high:
            budget.advice.append(f"Your {name} is {share:.0%} of the text. About 10% is usual, so the main "
                                 "points get the space.")
        elif share < low:
            budget.advice.append(f"Your {name} is only {share:.0%} of the text. Give it a few more sentences "
                                 f"(about 10% is usual).")
    return budget


@dataclass
class Effort:
    start: int
    end: int
    level: str  # "easy", "medium" or "hard"
    score: float
    words: int
    hard_words: int


def sentence_effort(text: str, passive: list[str] = ()) -> list[Effort]:
    """How hard each sentence is to read: length, long words (3+ syllables) and the passive voice.
    `passive` is the passive sentences found by nlp_checks.check()."""
    found = []
    for start, end in sentence_spans(text):
        sentence = text[start:end]
        words = WORD.findall(sentence)
        if len(words) < EFFORT_MIN_WORDS:
            continue
        hard = sum(1 for w in words if count_syllables(w) >= HARD_WORD_SYLLABLES)
        score = 0.5 * min(len(words) / (LONG_SENTENCE_WORDS + 10), 1) + 0.35 * min(hard / len(words) / 0.3, 1)
        if any(p.strip() and (p.strip() in sentence or sentence in p) for p in passive):
            score += 0.15
        level = next(name for limit, name in EFFORT_LEVELS if score < limit)
        found.append(Effort(start, end, level, round(score, 2), len(words), hard))
    return found


def effort_summary(efforts: list[Effort]) -> dict[str, int]:
    counts = Counter(e.level for e in efforts)
    return {level: counts.get(level, 0) for _, level in EFFORT_LEVELS}
