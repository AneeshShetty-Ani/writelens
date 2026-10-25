"""Check an essay against its assignment: the tasks the question sets (compare, evaluate...), the numbers
it asks for (two examples, five sources, 1,500 words), the topics it names, and the structure it expects.
Everything is word matching, so it shows signs that a requirement is met, not proof; the writer judges."""

import math
import re
from dataclasses import dataclass

from analysis import CITATION, REFERENCES_HEADING, WORD, paragraph_spans, split_paragraphs
from fixes import apply_fixes
from structure import content_words, stem

WORD_COUNT_SLACK = 0.1  # within 10% of a single word count counts as on target
MAX_TOPICS = 12
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                "ten": 10, "a couple of": 2, "several": 3}

# (label, words in the question that ask for it, signs in the essay that it was done)
TASKS = (
    ("Compare / contrast", r"compar\w*|contrast\w*|similarit\w*|differen\w*",
     ("similarly", "likewise", "both", "whereas", "in contrast", "unlike", "while", "on the other hand",
      "compared", "differs", "difference", "in common")),
    ("Evaluate / assess", r"evaluat\w*|assess\w*|critically|to what extent|how far",
     ("however", "strength", "weakness", "advantage", "disadvantage", "limitation", "effective", "benefit",
      "drawback", "overall", "outweigh")),
    ("Discuss both sides", r"discuss\w*|debate\w*",
     ("however", "on the other hand", "some argue", "others", "although", "alternatively", "critics", "while",
      "in contrast", "opponents")),
    ("Argue / justify", r"argu\w*|justif\w*|persuad\w*",
     ("because", "therefore", "evidence", "shows", "demonstrates", "thus", "this suggests", "clearly")),
    ("Explain causes and effects", r"explain\w*|why\b",
     ("because", "therefore", "as a result", "this means", "due to", "leads to", "causes", "so that", "since")),
    ("Analyse", r"analy[sz]\w*|examin\w*|investigat\w*",
     ("because", "suggests", "indicates", "shows", "this means", "reveals", "implies", "therefore")),
    ("Recommend", r"recommend\w*|propos\w*|suggest\w*",
     ("should", "recommend", "suggest", "propose", "it would be", "could be improved")),
    ("Define key terms", r"defin\w*",
     ("is defined as", "refers to", "means", "definition", "can be described as")),
    ("Reflect on your experience", r"reflect\w*|personal experience",
     ("i ", "my ", "i learned", "i learnt", "i realised", "i realized", "experience", "i felt")),
)
# task -> what to add, for the [TO DO] note in the improved version
TASK_HINTS = {
    "Compare / contrast": "compare them directly, e.g. “Unlike X, Y ...” or “Both ..., whereas ...”",
    "Evaluate / assess": "weigh strengths against limitations, e.g. “However, a limitation is ...”",
    "Discuss both sides": "give the other side too, e.g. “On the other hand, some argue ...”",
    "Argue / justify": "back your position with evidence, e.g. “This shows that ... because ...”",
    "Explain causes and effects": "explain why, e.g. “This happens because ...” or “As a result, ...”",
    "Analyse": "say what the evidence means, e.g. “This suggests that ...”",
    "Recommend": "give a recommendation, e.g. “It is recommended that ...”",
    "Define key terms": "define the key terms, e.g. “X refers to ...”",
    "Reflect on your experience": "add your own experience, e.g. “In my experience, ...”",
}
# what the question asks you to include -> (label, signs to count in the essay; None = can't be counted)
COUNTABLE = {
    "example": ("examples", r"\b(?:for example|for instance|such as|e\.g\.|to illustrate|an example)\b"),
    "source": ("sources", None),
    "reference": ("sources", None),
    "citation": ("sources", None),
    "study": ("sources", None),
    "paragraph": ("paragraphs", None),
    "reason": ("reasons", None),
    "factor": ("factors", None),
    "argument": ("arguments", None),
    "point": ("points", None),
    "case study": ("case studies", None),
}
QUANTITY = re.compile(
    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|a couple of|several)\s+(?:or more\s+)?"
    r"(?:(?:different|key|main|relevant|academic|scholarly|credible|reliable|peer[- ]reviewed|real[- ]world|"
    r"specific|separate|clear|well[- ]developed|body)\s+)*"
    r"(examples?|sources?|references?|citations?|stud(?:y|ies)|paragraphs?|reasons?|factors?|arguments?|"
    r"points?|case stud(?:y|ies))\b",
    re.IGNORECASE,
)
WORD_RANGE = re.compile(r"\b(\d{1,2},?\d{3}|\d{3})\s*(?:-|–|to|and)\s*(\d{1,2},?\d{3}|\d{3})[\s-]*words?\b", re.IGNORECASE)
WORD_COUNT = re.compile(r"\b(\d{1,2},?\d{3}|\d{3})[\s-]*words?\b", re.IGNORECASE)
REFERENCE_LIST = re.compile(r"reference list|bibliography|works cited|list of references", re.IGNORECASE)
CONCLUSION_SIGNS = re.compile(r"\b(?:in conclusion|to conclude|in summary|to sum up|overall|ultimately|"
                              r"in short|to summari[sz]e)\b", re.IGNORECASE)
# words in a question that are about the task, not its topic
NOT_TOPICS = set("""
essay assignment answer question task write writing discuss discussion explain evaluate evaluation assess
analyse analyze analysis compare comparison contrast argue argument justify define describe outline reflect
recommend propose suggest examine investigate critically extent include including provide give using words
word least example examples source sources reference references citation citations paragraph paragraphs
introduction conclusion report response marks mark page pages topic following based relevant must should
need needs will your you student students reason reasons factor factors point points case study studies
bibliography list cited work works format style apa mla harvard ieee chicago referencing approximately around
total maximum minimum limit range several different key main academic scholarly credible reliable peer reviewed
specific separate clear body discuss support supporting support evidence own view views opinion
one two three four five six seven eight nine ten
""".split())


@dataclass
class Requirement:
    group: str  # "Task", "Length", "Topic" or "Structure"
    label: str
    status: str  # "ok", "partial", "missing" or "check" (can't be checked automatically)
    detail: str
    todo: str = ""  # what to add, for a [TO DO] note in the improved version
    place: str = "body"  # where the note goes: "start", "body", "last" (end of the last paragraph), "end", "references"


def number(value: str) -> int:
    value = value.lower().replace(",", "")
    return int(value) if value.isdigit() else NUMBER_WORDS[value]


def phrase_count(phrase: str, text: str) -> int:
    phrase = phrase.strip()
    if phrase in ("i", "my"):  # "I" and "my" are counted as whole words
        return len(re.findall(rf"\b{phrase}\b", text, re.IGNORECASE))
    return len(re.findall(rf"\b{re.escape(phrase)}\b", text, re.IGNORECASE))


def without_references(essay: str) -> str:
    """The essay up to its reference list: the list's "(2020)" years aren't citations, and word limits
    usually leave it out."""
    m = REFERENCES_HEADING.search(essay)
    return essay[: m.start()] if m else essay


def sources_cited(essay: str) -> int:
    essay = without_references(essay)
    return len({re.sub(r"\s+", " ", m.group().lower()) for m in CITATION.finditer(essay)})


def check_tasks(question: str, essay: str) -> list[Requirement]:
    found = []
    for label, asks, signs in TASKS:
        if not re.search(rf"\b(?:{asks})", question, re.IGNORECASE):
            continue
        hits = {s.strip(): n for s in signs if (n := phrase_count(s, essay))}
        total = sum(hits.values())
        shown = ", ".join(f"“{s}”" for s in sorted(hits, key=lambda s: -hits[s])[:4])
        todo = f"{label.lower()}: {TASK_HINTS[label]}"
        if total >= 2:
            found.append(Requirement("Task", label, "ok", f"signs in your essay: {shown}"))
        elif total == 1:
            found.append(Requirement("Task", label, "partial", f"only one sign ({shown}); develop this part more", todo))
        else:
            found.append(Requirement("Task", label, "missing", "no signs of this in your essay yet", todo))
    return found


def check_quantities(question: str, essay: str) -> list[Requirement]:
    found, seen = [], set()
    for m in QUANTITY.finditer(question):
        wanted, noun = number(m.group(1)), m.group(2).lower()
        key = next(k for k in COUNTABLE if noun.startswith(k[:4]))  # "studies" -> "study", "examples" -> "example"
        label, signs = COUNTABLE[key]
        if label in seen:
            continue
        seen.add(label)
        title = f"{wanted} {label}"
        if label == "sources":
            have = sources_cited(essay)
        elif label == "paragraphs":
            have = len(split_paragraphs(essay))
        elif signs:
            have = len(re.findall(signs, essay, re.IGNORECASE))
        else:
            found.append(Requirement("Length", title, "check", f"count your {label} yourself"))
            continue
        status = "ok" if have >= wanted else "partial" if have else "missing"
        what = "different citations" if label == "sources" else "signs like “for example”" if label == "examples" else label
        more = f"add {wanted - have} more {label if wanted - have > 1 else label.rstrip('s')}"
        todo = "" if status == "ok" else more + {"sources": ", cited like (Author, Year)",
                                                 "examples": ", e.g. “For example, ...”"}.get(label, "")
        found.append(Requirement("Length", title, status, f"found {have} {what}", todo))
    return found


def check_length(question: str, essay: str) -> list[Requirement]:
    words = len(WORD.findall(without_references(essay)))
    if m := WORD_RANGE.search(question):
        low, high = number(m.group(1)), number(m.group(2))
    elif m := WORD_COUNT.search(question):
        target = number(m.group(1))
        low, high = math.ceil(target * (1 - WORD_COUNT_SLACK)), math.floor(target * (1 + WORD_COUNT_SLACK))
    else:
        return []
    label = f"{low:,}–{high:,} words"
    if words < low:
        return [Requirement("Length", label, "missing", f"you have {words:,}: {low - words:,} short")]
    if words > high:
        return [Requirement("Length", label, "missing", f"you have {words:,}: {words - high:,} over")]
    return [Requirement("Length", label, "ok", f"you have {words:,}")]


def question_topics(question: str) -> list[str]:
    """Content words of the question that aren't about the task itself, one per stem, in order."""
    topics, stems = [], set()
    for word in content_words(QUANTITY.sub(" ", question)):
        s = stem(word)
        if word in NOT_TOPICS or s in stems or len(word) < 4 or word.isdigit():
            continue
        stems.add(s)
        topics.append(word)
    return topics[:MAX_TOPICS]


def check_topics(question: str, essay: str) -> list[Requirement]:
    paragraphs = split_paragraphs(essay) or [essay]
    para_stems = [{stem(w) for w in content_words(p)} for p in paragraphs]
    essay_stems = [stem(w) for w in content_words(essay)]
    found = []
    for topic in question_topics(question):
        s = stem(topic)
        uses = essay_stems.count(s)
        where = [i for i, stems in enumerate(para_stems, 1) if s in stems]
        place = (f" (paragraph{'s' if len(where) > 1 else ''} {', '.join(map(str, where[:5]))})"
                 if len(paragraphs) > 1 and where else "")
        if uses >= 2:
            found.append(Requirement("Topic", topic, "ok", f"mentioned {uses} times{place}"))
        elif uses == 1:
            found.append(Requirement("Topic", topic, "partial", f"mentioned once{place}; is it covered enough?"))
        else:
            found.append(Requirement("Topic", topic, "missing", "not mentioned", f"say something about “{topic}”"))
    return found


def check_structure(question: str, essay: str) -> list[Requirement]:
    found = []
    paragraphs = split_paragraphs(essay)
    if re.search(r"\bconclu\w*", question, re.IGNORECASE):
        if len(paragraphs) >= 3 and CONCLUSION_SIGNS.search(paragraphs[-1]):
            found.append(Requirement("Structure", "Conclusion", "ok", "your last paragraph sums up"))
        elif len(paragraphs) >= 3:
            found.append(Requirement("Structure", "Conclusion", "partial",
                                     "your last paragraph doesn't read like a conclusion yet (e.g. “Overall, ...”)",
                                     "make this paragraph sum up your answer, e.g. start it with “Overall, ...”", "last"))
        else:
            found.append(Requirement("Structure", "Conclusion", "missing",
                                     f"your essay has {len(paragraphs)} paragraph(s); add a concluding one",
                                     "add a concluding paragraph that sums up your answer to the question", "end"))
    if re.search(r"\bintroduc\w*", question, re.IGNORECASE):
        if len(paragraphs) >= 3:
            found.append(Requirement("Structure", "Introduction", "ok", "your first paragraph"))
        else:
            found.append(Requirement("Structure", "Introduction", "missing", "split off an opening paragraph",
                                     "add an introduction that says what the essay will argue", "start"))
    if REFERENCE_LIST.search(question):
        if REFERENCES_HEADING.search(essay):
            found.append(Requirement("Structure", "Reference list", "ok", "found a References heading"))
        else:
            found.append(Requirement("Structure", "Reference list", "missing",
                                     "no “References” or “Bibliography” heading found",
                                     "list every source you cited, in your citation style", "references"))
    return found


def check_assignment(question: str, essay: str) -> list[Requirement]:
    return (check_tasks(question, essay) + check_length(question, essay) + check_quantities(question, essay)
            + check_structure(question, essay) + check_topics(question, essay))


def coverage(requirements: list[Requirement]) -> tuple[int, int]:
    """(requirements met, requirements that could be checked)."""
    checked = [r for r in requirements if r.status != "check"]
    return sum(r.status == "ok" for r in checked), len(checked)


def todo_note(text: str) -> str:
    return f"[TO DO: {text}]"


def improve_essay(essay: str, requirements: list[Requirement]) -> tuple[str, list[tuple[str, str, int]], int]:
    """The essay with the Writing Checker's safe fixes applied and a [TO DO] note wherever a requirement
    isn't met yet. Returns (text, fixes made, number of notes). The notes say what's needed; the writer
    adds the content."""
    fixed = apply_fixes(essay)
    text = fixed.text.rstrip()
    m = REFERENCES_HEADING.search(text)
    main, references = (text[: m.start()].rstrip(), text[m.start():]) if m else (text, "")
    todos: dict[str, list[str]] = {}
    for r in requirements:
        if r.todo:
            todos.setdefault(r.place, []).append(todo_note(r.todo))

    paragraphs = paragraph_spans(main)
    # the main body ends before the conclusion; with fewer than 3 paragraphs there is no separate conclusion
    body_end = paragraphs[-2][1] if len(paragraphs) >= 3 else len(main)
    last_end = paragraphs[-1][1] if paragraphs else len(main)
    inserts = [(body_end, " " + " ".join(todos["body"])) if "body" in todos else None,
               (last_end, " " + " ".join(todos["last"])) if "last" in todos else None,
               (len(main), "\n\n" + "\n\n".join(todos["end"])) if "end" in todos else None,
               (paragraphs[0][0] if paragraphs else 0, "\n\n".join(todos["start"]) + "\n\n") if "start" in todos else None]
    # from the end backwards, so earlier positions stay valid; at the same position the later note goes in
    # first, which leaves the notes in list order (body, last, end)
    for _, (pos, note) in sorted(((n, i) for n, i in enumerate(inserts) if i), key=lambda x: (-x[1][0], -x[0])):
        main = main[:pos] + note + main[pos:]
    if "references" in todos:
        references = "References\n\n" + "\n".join(todos["references"])
    improved = main + ("\n\n" + references if references else "")
    return improved, fixed.changes, sum(len(v) for v in todos.values())
