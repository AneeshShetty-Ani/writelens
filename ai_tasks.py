"""What the AI does in each tool: the request it gets, and the check its reply must pass before it's used.

Every check is strict on purpose. A quote must really be in the text it claims to come from, a rewrite must
stay about as long as the original, and a status must be one the app knows; anything else is dropped (or
the whole reply is rejected, so the next model is tried). The offline results are always there underneath.

Long texts are read in parts (cut at paragraph breaks), each sent as its own request, and the answers are
put back together with their positions shifted to match the whole text, so no part goes unchecked.
"""

import re
from dataclasses import dataclass
from typing import Callable

from analysis import WORD

PART_CHARS = 10_000  # about 1,700 words: one request each, so a whole 200,000-character text is 20 parts
MAX_PARTS = 20
ESSAY_PART_CHARS = 30_000  # the assignment check needs as much of the essay at once as it can get
DRAFT_PART_CHARS = 8_000  # plagiarism: each part of the draft is compared with each group of sources
SOURCE_GROUP_CHARS = 40_000  # about 10,000 tokens: well inside the free models' context windows
PAGE_TEXT_CHARS = 12_000  # a web page's text, read for its author and date
MAX_AI_ISSUES = 8  # per part
REWRITE_LENGTH = (0.5, 1.4)  # the rewrite's word count, as a share of the original's (cutting wordiness shortens it)
MAX_PARAPHRASES = 8
STATUSES = ("ok", "partial", "missing")
STATUS_RANK = {"missing": 0, "partial": 1, "ok": 2}
MAX_EXTRA_REQUIREMENTS = 3
COUNTED_WORDS = {"word", "words", "source", "sources", "example", "examples", "citation", "citations",
                 "reference", "references", "paragraph", "paragraphs", "length", "limit"}
KINDS = ("article", "book", "web")
YEAR = re.compile(r"(1[5-9]|20)\d{2}")


def find_quote(text: str, quote: str) -> tuple[int, int] | None:
    """Where `quote` is in `text`, ignoring case and differences in spacing; None if it isn't there."""
    words = re.findall(r"\w+", quote) if quote else []
    if not words:
        return None
    pattern = r"\W+".join(re.escape(w) for w in words)
    m = re.search(rf"\b{pattern}\b", text, re.IGNORECASE)
    return (m.start(), m.end()) if m else None


def clean(value, limit: int = 400) -> str:
    return " ".join(str(value or "").split())[:limit]


def parts(text: str, size: int = PART_CHARS) -> list[tuple[int, int]]:
    """(start, end) of pieces of `text` at most `size` long, cut at a paragraph break where possible (else
    a line break, a sentence end or a space). The whitespace between pieces belongs to none of them."""
    spans, pos, n = [], 0, len(text)
    while pos < n:
        while pos < n and text[pos].isspace():
            pos += 1
        if pos == n:
            break
        end = min(pos + size, n)
        if end < n:
            window = text[pos:end]
            for sep in ("\n\n", "\n", ". ", " "):
                cut = window.rfind(sep)
                if cut > size // 2:
                    end = pos + cut + (1 if sep == ". " else 0)
                    break
        last = end
        while last > pos and text[last - 1].isspace():
            last -= 1
        spans.append((pos, last))
        pos = end
    return spans


def part_note(number: int, total: int, what: str) -> str:
    return f" This is part {number} of {total} of the {what}; judge only this part." if total > 1 else ""


# ---- Writing --------------------------------------------------------------------------

@dataclass
class AiIssue:
    start: int  # where the quote is in the text
    end: int
    quote: str  # exactly as in the text
    problem: str
    fix: str


@dataclass
class WritingReview:
    issues: list[AiIssue]
    improved: str  # "" when there's no AI rewrite (it failed its check)
    offline_parts: int = 0  # parts of a long text whose rewrite fell back to the rule-based version


def writing_task(text: str) -> tuple[str, int]:
    """(the request, max answer tokens) for one part of the text."""
    task = (
        "Review this student's text like a careful teacher. Find up to "
        f"{MAX_AI_ISSUES} problems that simple rule-based checkers miss: grammar and agreement errors, unclear "
        "or ambiguous sentences, wrong word choice, missing words, weak logic or unsupported claims, abrupt "
        "jumps between ideas. Skip spelling typos and wordy phrases (already checked).\n"
        'Return {"issues": [{"quote": "<exact words from the text, 3 to 25 words>", "problem": "<what is wrong, '
        'one sentence>", "fix": "<how to fix it, one sentence>"}], "improved": "<the whole text with grammar, '
        "clarity and flow improved. Keep the writer's meaning, ideas, voice, paragraph breaks and any "
        "citations. Don't add new facts, arguments or sources, and don't make it much longer or shorter>\"}\n\n"
        f"The text:\n<<<\n{text[:PART_CHARS]}\n>>>"
    )
    return task, 900 + len(text) // 3


def accept_writing(text: str):
    def accept(data: dict) -> WritingReview | None:
        raw = data.get("issues")
        if not isinstance(raw, list):
            return None
        issues = []
        for item in raw[:MAX_AI_ISSUES]:
            if not isinstance(item, dict) or not (span := find_quote(text, clean(item.get("quote")))):
                continue
            problem, fix = clean(item.get("problem")), clean(item.get("fix"))
            if problem:
                issues.append(AiIssue(span[0], span[1], text[span[0]:span[1]], problem, fix))
        improved = str(data.get("improved") or "").strip()
        words, new_words = len(WORD.findall(text)), len(WORD.findall(improved))
        low, high = REWRITE_LENGTH
        if not (words and low * words <= new_words <= high * words) or improved == text.strip():
            improved = ""
        return WritingReview(issues, improved)
    return accept


def combine_writing(text: str, spans: list[tuple[int, int]], reviews: list, fallback: Callable[[str], str]) -> WritingReview:
    """One review of the whole text from the reviews of its parts (None where a part's request failed).
    A part without an AI rewrite gets `fallback(part)`, the rule-based version, so the text stays whole."""
    issues, pieces, offline = [], [], 0
    for i, ((start, end), review) in enumerate(zip(spans, reviews)):
        if review:
            issues += [AiIssue(start + x.start, start + x.end, x.quote, x.problem, x.fix) for x in review.issues]
        if review and review.improved:
            pieces.append(review.improved)
        else:
            pieces.append(fallback(text[start:end]))
            offline += 1
        if i + 1 < len(spans):
            pieces.append(text[end:spans[i + 1][0]])  # the paragraph break between parts
    return WritingReview(issues, "".join(pieces) if offline < len(spans) else "", offline)


# ---- Assignment ---------------------------------------------------------------------------

@dataclass
class Judgement:
    status: str  # one of STATUSES
    reason: str
    hint: str  # what to add, when it isn't fully covered


@dataclass
class AssignmentReview:
    judged: dict[int, Judgement]  # requirement index -> the AI's judgement
    extra: list[tuple[str, Judgement]]  # requirements the offline checks didn't find: (label, judgement)


def judged_by_ai(requirement) -> bool:
    """Exact counts (words, citations, examples, paragraphs) stay offline; the AI judges meaning."""
    return requirement.group != "Length" or requirement.status == "check"


def assignment_task(question: str, essay: str, requirements, part: tuple[int, int] = (1, 1)) -> tuple[str, int]:
    """The request for one part of the essay (`part` = (its number, how many there are))."""
    items = "\n".join(f"{i}. {r.label}" for i, r in enumerate(requirements) if judged_by_ai(r))
    task = (
        "Judge how well a student's essay meets its assignment, by meaning rather than keywords."
        + part_note(*part, "essay") + "\n"
        f"For each numbered requirement below, decide: \"ok\" (fully covered), \"partial\" (touched on but thin) "
        "or \"missing\". Give the reason in one sentence that points to where in the essay (or what is absent). "
        "For partial or missing ones, give a hint: one sentence on what kind of point or evidence to add and "
        "where. Don't write the content for them.\n"
        f"Also list up to {MAX_EXTRA_REQUIREMENTS} other things the question clearly asks for that aren't covered "
        "by the list, judged the same way. Don't repeat anything already listed, and leave out word counts, "
        "numbers of sources or examples (those are counted separately).\n"
        'Return {"requirements": [{"id": <number>, "status": "...", "reason": "...", "hint": "..."}], '
        '"extra": [{"label": "<short name>", "status": "...", "reason": "...", "hint": "..."}]}\n\n'
        f"Requirements:\n{items}\n\nThe question:\n<<<\n{question[:3000]}\n>>>\n\n"
        f"The essay:\n<<<\n{essay[:ESSAY_PART_CHARS]}\n>>>"
    )
    return task, 1500


def judgement(item: dict) -> Judgement | None:
    status = clean(item.get("status")).lower()
    if status not in STATUSES:
        return None
    hint = clean(item.get("hint")) if status != "ok" else ""
    return Judgement(status, clean(item.get("reason")), hint)


def repeats_a_requirement(label: str, requirements) -> bool:
    """An extra requirement that's really one already listed, or a count the offline checks handle."""
    words = set(re.findall(r"[a-z]+", label.lower()))
    if words & COUNTED_WORDS:
        return True
    return any(words & set(re.findall(r"[a-z]{4,}", r.label.lower())) for r in requirements)


def accept_assignment(requirements):
    allowed = {i for i, r in enumerate(requirements) if judged_by_ai(r)}

    def accept(data: dict) -> AssignmentReview | None:
        raw = data.get("requirements")
        if not isinstance(raw, list):
            return None
        judged = {}
        for item in raw:
            if isinstance(item, dict) and (j := judgement(item)):
                try:
                    index = int(item.get("id"))
                except (TypeError, ValueError):
                    continue
                if index in allowed:
                    judged[index] = j
        if allowed and not judged:
            return None
        extra = []
        for item in data.get("extra") or []:
            if (isinstance(item, dict) and (label := clean(item.get("label"), 60)) and (j := judgement(item))
                    and not repeats_a_requirement(label, requirements)):
                extra.append((label, j))
        return AssignmentReview(judged, extra[:MAX_EXTRA_REQUIREMENTS])
    return accept


def combine_assignment(reviews: list) -> AssignmentReview:
    """The reviews of an essay's parts as one: a requirement met in any part is met, so the best status wins."""
    judged: dict[int, Judgement] = {}
    extra: dict[str, tuple[str, Judgement]] = {}
    better = lambda new, old: old is None or STATUS_RANK[new.status] > STATUS_RANK[old.status]  # noqa: E731
    for review in filter(None, reviews):
        for i, j in review.judged.items():
            if better(j, judged.get(i)):
                judged[i] = j
        for label, j in review.extra:
            if better(j, extra.get(label.lower(), (None, None))[1]):
                extra[label.lower()] = (label, j)
    return AssignmentReview(judged, list(extra.values())[:MAX_EXTRA_REQUIREMENTS])


def merge_assignment(requirements, review: AssignmentReview, requirement_type):
    """The requirements with the AI's judgements in place of the keyword ones, plus its extra ones.
    `requirement_type` is assignment.Requirement (passed in to keep this module free of page logic)."""
    merged = []
    for i, r in enumerate(requirements):
        j = review.judged.get(i)
        if j is None:
            merged.append(r)
            continue
        todo = f"{r.label.lower()}: {j.hint}" if j.hint else ""
        # notes about the introduction, conclusion and references keep their place in the essay
        merged.append(requirement_type(r.group, r.label, j.status, j.reason, todo, r.place))
    for label, j in review.extra:
        merged.append(requirement_type("Task", label, j.status, j.reason, f"{label.lower()}: {j.hint}" if j.hint else ""))
    return merged


# ---- Plagiarism ------------------------------------------------------------------------------

@dataclass
class Paraphrase:
    start: int  # in the draft
    end: int
    source: str  # source name
    source_quote: str  # the matching words in the source, or "" if the AI's quote wasn't found
    why: str


def plagiarism_parts(sources: dict[str, str], draft: str) -> list[tuple[tuple[int, int], dict[str, str]]]:
    """Every (part of the draft, group of sources) pair to compare. Sources are packed into groups that
    fit one request; a long source is split across groups, each holding one piece of it."""
    groups, current, size = [], {}, 0
    for name, text in sources.items():
        for s, e in parts(text, SOURCE_GROUP_CHARS):
            if current and (size + e - s > SOURCE_GROUP_CHARS or name in current):
                groups.append(current)
                current, size = {}, 0
            current[name] = text[s:e]
            size += e - s
    if current:
        groups.append(current)
    return [(span, group) for span in parts(draft, DRAFT_PART_CHARS) for group in groups]


def plagiarism_task(sources: dict[str, str], draft: str) -> tuple[str, int]:
    listed = "\n\n".join(f"SOURCE \"{name}\":\n<<<\n{text[:SOURCE_GROUP_CHARS]}\n>>>" for name, text in sources.items())
    task = (
        "Find passages in the draft that take an idea from a source and reword it (paraphrase) closely: same "
        "meaning and order of ideas, different words. Ignore word-for-word copying (already found), common "
        "knowledge, and passages that cite the source.\n"
        f"Return up to {MAX_PARAPHRASES}: "
        '{"paraphrases": [{"draft": "<exact words from the draft>", "source": "<source name>", '
        '"source_quote": "<exact words from that source>", "why": "<one sentence>"}]}. '
        'Return {"paraphrases": []} if there are none.\n\n'
        f"{listed}\n\nTHE DRAFT:\n<<<\n{draft[:DRAFT_PART_CHARS]}\n>>>"
    )
    return task, 1200


def accept_plagiarism(sources: dict[str, str], draft: str):
    def accept(data: dict) -> list[Paraphrase] | None:
        raw = data.get("paraphrases")
        if not isinstance(raw, list):
            return None
        found, used = [], []
        for item in raw[:MAX_PARAPHRASES]:
            if not isinstance(item, dict) or not (span := find_quote(draft, clean(item.get("draft"), 2000))):
                continue
            if any(span[0] < e and s < span[1] for s, e in used):
                continue  # overlaps one already found
            name = clean(item.get("source"), 200)
            if name not in sources:
                name = next(iter(sources)) if len(sources) == 1 else ""
            source_span = find_quote(sources.get(name, ""), clean(item.get("source_quote"), 2000))
            if not name or source_span is None:
                continue  # can't show where in a source it came from, so it may be made up
            used.append(span)
            found.append(Paraphrase(span[0], span[1], name, sources[name][source_span[0]:source_span[1]],
                                    clean(item.get("why"))))
        return sorted(found, key=lambda p: p.start)
    return accept


def combine_plagiarism(jobs: list, results: list) -> list[Paraphrase]:
    """The paraphrases found in each (draft part, sources) job, placed in the whole draft, without overlaps."""
    found: list[Paraphrase] = []
    for ((start, _), _), result in zip(jobs, results):
        for p in result or []:
            s, e = start + p.start, start + p.end
            if not any(s < q.end and q.start < e for q in found):
                found.append(Paraphrase(s, e, p.source, p.source_quote, p.why))
    return sorted(found, key=lambda p: p.start)


# ---- Compare ------------------------------------------------------------------------------
# Compare uses the plagiarism check, with Document B as the source.


# ---- Citations ----------------------------------------------------------------------------

def citation_task(text: str) -> tuple[str, int]:
    task = (
        "Turn this reference, written any way, into fields. Use only what is in the text: leave a field empty "
        "rather than guess, and never invent authors, years or titles. Authors as \"Family, Given\".\n"
        'Return {"kind": "article" | "book" | "web", "title": "", "authors": [], "year": "", '
        '"container": "<journal, publisher or website>", "volume": "", "issue": "", "pages": "", "doi": "", '
        '"url": ""}\n\n'
        f"The reference:\n<<<\n{text[:1500]}\n>>>"
    )
    return task, 500


def family(author: str) -> str:
    """"Austen, Jane" or "Jane Austen" -> "austen"."""
    name = author.split(",")[0] if "," in author else (author.split() or [""])[-1]
    return name.strip().lower()


def family_first(author: str) -> str:
    """"Jane Austen" -> "Austen, Jane", the form the citation styles expect; "Austen, Jane" stays."""
    if "," in author or " " not in author:
        return author
    given, last = author.rsplit(" ", 1)
    return f"{last}, {given}"


def accept_citation(text: str):
    def accept(data: dict) -> dict | None:
        title = clean(data.get("title"), 300)
        if not title or not find_quote(text, title):
            return None  # the title must come from what the user typed
        lower = text.lower()
        # an author counts only if their family name was typed; other fields only if their value was
        authors = [family_first(a) for a in (clean(x, 120) for x in data.get("authors") or [])
                   if a and family(a) in lower]
        year = clean(data.get("year"), 10)
        fields = {
            "kind": data.get("kind") if data.get("kind") in KINDS else "article",
            "title": title,
            "authors": authors,
            "year": year if re.fullmatch(r"\d{4}", year) and year in text else "",
        }
        for name in ("container", "volume", "issue", "pages", "doi", "url"):
            value = clean(data.get(name), 300)
            fields[name] = value if value and value.lower() in lower else ""
        return fields
    return accept


def web_details_task(title: str, page_text: str) -> tuple[str, int]:
    """Ask for a web page's author and year when its metadata doesn't give them."""
    task = (
        f"This is the text of a web page titled \"{clean(title, 200)}\". Find who wrote it (people named as its "
        "author, e.g. in a byline like \"By Jane Smith\"; an organisation only if no person is named) and the "
        "year it was published or last updated. Leave a field empty if the text doesn't say; don't guess.\n"
        'Return {"authors": ["<name exactly as written>"], "year": ""}\n\n'
        f"The page:\n<<<\n{page_text[:PAGE_TEXT_CHARS]}\n>>>"
    )
    return task, 300


def accept_web_details(page_text: str):
    def accept(data: dict) -> dict | None:
        names = data.get("authors")
        if not isinstance(names, list):
            return None
        page = page_text[:PAGE_TEXT_CHARS]
        # a name or year counts only if it's really on the page
        authors = [family_first(a) for a in (clean(x, 80) for x in names[:6]) if a and find_quote(page, a)]
        year = clean(data.get("year"), 10)
        return {"authors": authors, "year": year if YEAR.fullmatch(year) and year in page else ""}
    return accept


# ---- Feedback -------------------------------------------------------------------------------

def feedback_task(category: str, title: str, description: str) -> tuple[str, int]:
    task = (
        "Tidy up this feedback about the WriteLens app so it makes a clear GitHub issue for its developer. Keep "
        "every detail and the writer's meaning, and add nothing new: no guessed steps, versions or causes. Fix "
        "spelling and grammar. Give a short, specific title (under 80 characters) and a description in Markdown. "
        "For a bug report, use the headings \"### What happened\", \"### Steps to reproduce\" and \"### What I "
        "expected\"; otherwise \"### The problem\" and \"### The idea\". Leave out a heading the writer gave no "
        "information for.\n"
        'Return {"title": "...", "description": "..."}\n\n'
        f"Category: {category}\nTitle:\n<<<\n{title[:200]}\n>>>\nDescription:\n<<<\n{description[:4000]}\n>>>"
    )
    return task, 900


def accept_feedback(title: str, description: str):
    words = len(WORD.findall(f"{title} {description}"))

    def accept(data: dict) -> dict | None:
        new_title = clean(data.get("title"), 120)
        new_description = str(data.get("description") or "").strip()
        if not new_title or (description.strip() and not new_description):
            return None
        # headings add a few words; much more than that means the AI added things the writer didn't say
        if len(WORD.findall(f"{new_title} {new_description}")) > 2 * words + 30:
            return None
        return {"title": new_title, "description": new_description}
    return accept
