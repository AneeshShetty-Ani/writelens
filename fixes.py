"""Safe automatic edits for the Writing Checker: shorter forms of wordy phrases and dropped filler words.
Anything that needs judgement (passive voice, long sentences) is left to the writer."""

import re
from dataclasses import dataclass, field

# wordy phrase -> replacement ("" deletes it). Only phrases whose replacement reads correctly in
# nearly any sentence; "in terms of" or "the fact that" need a human to reword the sentence.
REPLACEMENTS = {
    "it is very important to note that": "",
    "it is important to note that": "",
    "it should be noted that": "",
    "it can be said that": "",
    "needless to say": "",
    "due to the fact that": "because",
    "in spite of the fact that": "although",
    "at the end of the day": "ultimately",
    "a large number of": "many",
    "at this point in time": "now",
    "in the near future": "soon",
    "in the event that": "if",
    "has the ability to": "can",
    "first and foremost": "first",
    "each and every": "every",
    "over the course of": "during",
    "in order to": "to",
    "prior to": "before",
    "with regard to": "about",
    "is able to": "can",
}
FILLERS = ("really", "very", "basically", "actually", "literally", "totally")
# "very much", "not really": dropping the filler here changes the meaning or the grammar
KEEP_BEFORE = {"much", "many", "few", "little", "well"}
KEEP_AFTER = {"not", "never"}
CAP = "\x01"  # marks a deletion at the start of a sentence, so the next word gets a capital


@dataclass
class FixResult:
    text: str
    changes: list[tuple[str, str, int]] = field(default_factory=list)  # (phrase, replacement, count)


def at_sentence_start(text: str, pos: int) -> bool:
    before = text[:pos].rstrip(" \t")
    return not before or before[-1] in ".!?\n" + CAP


def apply_fixes(text: str) -> FixResult:
    result = FixResult(text)
    for phrase in sorted(REPLACEMENTS, key=len, reverse=True):
        replacement = REPLACEMENTS[phrase]
        # a deleted phrase takes its trailing comma and space with it
        pattern = rf"\b{re.escape(phrase)}\b" + ("" if replacement else r",?\s*")
        count = 0

        def swap(m: re.Match) -> str:
            nonlocal count
            count += 1
            if not replacement:
                return CAP if at_sentence_start(m.string, m.start()) else ""
            return replacement[0].upper() + replacement[1:] if m.group(0)[0].isupper() else replacement

        result.text = re.sub(pattern, swap, result.text, flags=re.IGNORECASE)
        if count:
            result.changes.append((phrase, replacement, count))

    filler_counts: dict[str, int] = {}

    def drop(m: re.Match) -> str:
        word = m.group(1).lower()
        following = m.string[m.end():].split(maxsplit=1)
        preceding = m.string[: m.start()].split()
        if (following and following[0].lower().strip(",.") in KEEP_BEFORE) or (
            preceding and (preceding[-1].lower() in KEEP_AFTER or preceding[-1].lower().endswith("n't"))
        ):
            return m.group(0)
        filler_counts[word] = filler_counts.get(word, 0) + 1
        return CAP if at_sentence_start(m.string, m.start()) else ""

    result.text = re.sub(rf"\b({'|'.join(FILLERS)})\b,?[ \t]+", drop, result.text, flags=re.IGNORECASE)
    result.changes += [(w, "", n) for w, n in filler_counts.items()]

    result.text = re.sub(CAP + r"+(\W*)(\w)", lambda m: m.group(1) + m.group(2).upper(), result.text)
    result.text = re.sub(r"[ \t]{2,}", " ", result.text.replace(CAP, ""))
    return result
