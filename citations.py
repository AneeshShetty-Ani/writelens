"""References: DOI lookup, citation styles, [@key] marker insertion, BibTeX / CSL-JSON / LaTeX export."""

import json
import re
import urllib.parse
from dataclasses import asdict, dataclass, field

import requests

STYLES = ("IEEE", "APA", "MLA", "Harvard", "Chicago")  # Chicago = author-date (17th ed.)
KINDS = {"article": "Journal article", "book": "Book", "web": "Web page"}
CROSSREF_URL = "https://api.crossref.org/works/"
OPENLIBRARY_URL = "https://openlibrary.org/api/books"
OPENLIBRARY_HEADERS = {"User-Agent": "WriteLens citation lookup (https://github.com/AneeshShetty-Ani/writelens)"}
TIMEOUT = 10
# [@key] or [@key1; @key2]
MARKER = re.compile(r"\[@([\w:-]+(?:\s*;\s*@[\w:-]+)*)\]")
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")


class CitationError(Exception):
    pass


@dataclass
class Reference:
    key: str
    kind: str  # one of KINDS
    title: str
    authors: list[str] = field(default_factory=list)  # "Family, Given"
    year: str = ""
    container: str = ""  # journal (article), publisher (book) or site name (web)
    volume: str = ""
    issue: str = ""
    pages: str = ""
    doi: str = ""
    url: str = ""


# ---- names ------------------------------------------------------------------

def split_name(author: str) -> tuple[str, str]:
    """Return (family, given). Accepts "Family, Given" or "Given Family"."""
    author = author.strip()
    if "," in author:
        family, given = author.split(",", 1)
        return family.strip(), given.strip()
    parts = author.split()
    return (parts[-1], " ".join(parts[:-1])) if len(parts) > 1 else (author, "")


def initials(given: str) -> str:
    return " ".join(f"{p[0]}." for p in re.split(r"[\s.]+", given) if p)


def make_key(authors: list[str], year: str, existing: set[str]) -> str:
    family = split_name(authors[0])[0] if authors else "ref"
    base = re.sub(r"[^a-z0-9]", "", family.lower()) or "ref"
    base += re.sub(r"\D", "", year)
    key, n = base, 0
    while key in existing:
        key = base + "abcdefghijklmnopqrstuvwxyz"[n % 26] * (n // 26 + 1)
        n += 1
    return key


# ---- DOI lookup -------------------------------------------------------------

def normalize_doi(doi: str) -> str:
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi.strip(), flags=re.IGNORECASE)
    if not DOI_RE.match(doi):
        raise CitationError("That doesn't look like a DOI. It should start with 10., like 10.1038/nature14539.")
    return doi


def lookup_doi(doi: str, existing: set[str]) -> Reference:
    doi = normalize_doi(doi)
    try:
        resp = requests.get(CROSSREF_URL + urllib.parse.quote(doi), timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise CitationError("Could not reach Crossref. Check your connection and try again.") from exc
    if resp.status_code == 404:
        raise CitationError(f"No record found for DOI {doi}.")
    try:
        resp.raise_for_status()
        msg = resp.json()["message"]
    except (requests.RequestException, ValueError, KeyError) as exc:
        raise CitationError("Crossref returned an unexpected response. Please try again.") from exc
    return from_crossref(msg, existing)


def from_crossref(msg: dict, existing: set[str]) -> Reference:
    authors = [
        f"{a['family']}, {a.get('given', '')}".strip(", ") if "family" in a else a.get("name", "")
        for a in msg.get("author", [])
    ]
    authors = [a for a in authors if a]
    date_parts = (msg.get("issued") or msg.get("published") or {}).get("date-parts") or [[None]]
    year = str(date_parts[0][0] or "")
    kind = "book" if msg.get("type", "").startswith("book") else "article"
    first = lambda v: (v[0] if isinstance(v, list) and v else v) or ""  # noqa: E731
    return Reference(
        key=make_key(authors, year, existing),
        kind=kind,
        title=first(msg.get("title")),
        authors=authors,
        year=year,
        container=first(msg.get("publisher")) if kind == "book" else first(msg.get("container-title")),
        volume=msg.get("volume", ""),
        issue=msg.get("issue", ""),
        pages=msg.get("page", ""),
        doi=msg.get("DOI", ""),
        url=msg.get("URL", ""),
    )


# ---- a reference written any way ---------------------------------------------

DOI_IN_TEXT = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+")
ISBN_IN_TEXT = re.compile(r"\bISBN(?:-1[03])?:?\s*([\dXx][\d\s-]{8,16}[\dXx])\b", re.IGNORECASE)
TITLE_MATCH_SHARE = 0.8  # share of a Crossref title's words that must be in the text to count as the same work


def title_matches(title: str, text: str) -> bool:
    """Whether a found title is really the one in `text`: most of its words (3+ letters) must appear there."""
    words = [w for w in re.findall(r"[a-z0-9]+", title.lower()) if len(w) >= 3]
    have = set(re.findall(r"[a-z0-9]+", text.lower()))
    return len(words) >= 2 and sum(w in have for w in words) / len(words) >= TITLE_MATCH_SHARE


def crossref_search(query: str, existing: set[str], check_against: str = "", year: str = "") -> Reference | None:
    """The best Crossref match for a free-text reference, if its title is really in `check_against`
    (default: the query) and, when `year` is given, it's from that year; None if nothing matches or Crossref
    can't be reached."""
    try:
        resp = requests.get(CROSSREF_URL.rstrip("/"), params={"query.bibliographic": query[:500], "rows": 3},
                            timeout=TIMEOUT)
        resp.raise_for_status()
        items = resp.json()["message"]["items"]
    except (requests.RequestException, ValueError, KeyError):
        return None
    for msg in items:
        title = (msg.get("title") or [""])[0]
        if title and title_matches(title, check_against or query):
            ref = from_crossref(msg, existing)
            if not year or ref.year == year:
                return ref
    return None


YEAR_IN_TEXT = re.compile(r"\b(1[5-9]\d{2}|20\d{2})[a-z]?\b")
URL_IN_TEXT = re.compile(r"https?://\S+")
QUOTED_TITLE = re.compile(r"[\"“](.+?)[\"”]")
APA_START = re.compile(r"(.+?)\s*\((1[5-9]\d{2}|20\d{2})[a-z]?(?:,[^)]*)?\)[.,]?\s*(.+)")
# a full stop that ends a part of a reference: not the one after an initial ("J."), "et al." or "vol."
PART_END = re.compile(r"(?<!\b[A-Z])(?<!\bet al)(?<!\bvol)(?<!\bno)(?<!\bpp)(?<!\bp)[.?!](?=\s|$)", re.IGNORECASE)
INITIALS = re.compile(r"(?:[A-Z]\.?\s*)*[A-Z]\.?")
# "Austen, J." or "LeCun, Y., Bengio, Y., & Hinton, G." at the start of a reference
INITIALED_NAMES = re.compile(r"(?:[A-Z][\w'’-]+,\s*(?:[A-Z]\.\s*)+(?:,|,?\s*(?:&|and)\b)?\s*)+")
ARTICLE_SIGNS = re.compile(r"\bvol\.|\bno\.\s*\d|\bpp?\.\s*\d|\b\d+\s*\(\d+[\w-]*\)", re.IGNORECASE)
EDITION = re.compile(r"^\d+(?:st|nd|rd|th) (?:edn|ed|edition)\b|^(?:edited|ed\.|eds\.)", re.IGNORECASE)


def reference_parts(text: str) -> list[str]:
    """'Smith, J. A. Title here? Publisher.' -> ['Smith, J. A', 'Title here?', 'Publisher']."""
    out, pos = [], 0
    for m in PART_END.finditer(text):
        piece = text[pos:m.end() if m.group() in "?!" else m.start()].strip(" ,;:")
        if piece:
            out.append(piece)
        pos = m.end()
    if rest := text[pos:].strip(" .,;:"):
        out.append(rest)
    return out


def parse_authors(part: str) -> list[str]:
    """Names as typed in any common style -> ["Family, Given", ...]: "LeCun, Y., & Bengio, Y.",
    "Y. LeCun and Y. Bengio", "Austen, Jane", "Smith, John, and Jane Doe"."""
    part = re.sub(r"\bet al\b\.?", "", part)
    part = re.sub(r"\s*,?\s*(?:&|\band\b)\s*", ", ", part).strip(" .,;:")
    tokens = [t.strip() for t in re.split(r"[;,]", part) if t.strip()]
    authors, i = [], 0
    while i < len(tokens):
        name, after = tokens[i], tokens[i + 1] if i + 1 < len(tokens) else ""
        if " " not in name.strip(".") and after and (INITIALS.fullmatch(after) or " " not in after):
            if INITIALS.fullmatch(after) and not after.endswith("."):
                after += "."  # the final full stop was taken as the end of the names
            authors.append(f"{name.rstrip('.')}, {after}")  # "Family, Given" split by the comma
            i += 2
            continue
        family, given = split_name(name if INITIALS.search(name) else name.rstrip("."))
        authors.append(f"{family}, {given}".strip(", "))
        i += 1
    return authors


def parse_reference(text: str) -> dict | None:
    """Read a reference written in a common style (APA, Harvard, MLA, Chicago, IEEE) without AI or the
    internet. Returns the same fields as the AI's reading, or None when the text has no recognisable
    shape (e.g. a list of keywords); the result should still be checked, since styles vary."""
    text = " ".join(text.split())
    url = m.group().rstrip(".,;)") if (m := URL_IN_TEXT.search(text)) else ""
    body = re.sub(r"\b(?:Retrieved from|Available(?: at)?:?|\[Online\]\.?)\s*", "", URL_IN_TEXT.sub("", text),
                  flags=re.IGNORECASE).strip(" .,")
    year = m.group(1) if (m := YEAR_IN_TEXT.search(body)) else ""
    if q := QUOTED_TITLE.search(body):  # MLA, Chicago, IEEE: the title is in quotation marks
        names, title, rest = body[:q.start()], q.group(1).strip(" .,"), body[q.end():]
        rest_parts = reference_parts(rest.strip(" .,"))
    elif m := APA_START.match(body):  # APA, Harvard: Authors (Year). Title. Journal or publisher.
        names, year = m.group(1), m.group(2)
        title, *rest_parts = reference_parts(m.group(3)) or [""]
    else:  # MLA / Chicago books: Authors. [Year.] Title. Publisher, Year.
        names = m.group() if (m := INITIALED_NAMES.match(body)) else ""
        pieces = [p for p in reference_parts(body[len(names):]) if not YEAR_IN_TEXT.fullmatch(p)]
        if not names and pieces:
            names, pieces = pieces[0], pieces[1:]
        if not names or not pieces:
            return None
        title, *rest_parts = pieces
    authors = parse_authors(names)
    if len(title) < 2 or not (authors or year):
        return None
    rest = " ".join(rest_parts)
    article = bool(ARTICLE_SIGNS.search(rest))
    rest_parts = [p for p in rest_parts if not EDITION.match(p)]
    # a journal or website comes straight after the title; a book's publisher comes last
    where = (rest_parts[0] if article or url else rest_parts[-1]) if rest_parts else ""
    container = re.split(r",\s*(?:vol\.|no\.|pp?\.|\d)|\s+\d", where, maxsplit=1, flags=re.IGNORECASE)[0]
    container = re.sub(r"^(?:In:?|[A-Z][a-z]+:)\s+", "", container.strip(" .,:"))  # "London: Penguin" -> "Penguin"
    volume = issue = pages = ""
    if article:
        if m := re.search(r"\bvol\.\s*(\d+)|\b(\d+),\s*no\.", rest, re.IGNORECASE):
            volume = m.group(1) or m.group(2)
        if m := re.search(r"\bno\.\s*(\d+)", rest, re.IGNORECASE):
            issue = m.group(1)
        if not volume and (m := re.search(r"\b(\d+)\s*\((\d+[\w-]*)\)", rest)) and m.group(2) != year:
            volume, issue = m.group(1), m.group(2)
        if m := re.search(r"\b(\d+\s*[-–]\s*\d+)\b", rest):
            pages = re.sub(r"\s", "", m.group(1))
    return {"kind": "article" if article else "web" if url else "book", "title": title.rstrip("."),
            "authors": authors, "year": year, "container": container, "volume": volume, "issue": issue,
            "pages": pages, "doi": "", "url": url}


def from_fields(fields: dict, existing: set[str]) -> Reference:
    """A Reference from a dict of its fields (as the AI reads them from a pasted reference)."""
    return Reference(key=make_key(fields["authors"], fields["year"], existing), kind=fields["kind"],
                     title=fields["title"], authors=fields["authors"], year=fields["year"],
                     **{k: fields.get(k, "") for k in ("container", "volume", "issue", "pages", "doi", "url")})


# ---- ISBN lookup ------------------------------------------------------------

def normalize_isbn(isbn: str) -> str:
    """Digits of an ISBN-10 or ISBN-13, after checking its check digit."""
    raw = re.sub(r"^\s*isbn(?:-1[03])?:?", "", isbn.strip(), flags=re.IGNORECASE)
    digits = re.sub(r"[\s-]", "", raw).upper()
    if re.fullmatch(r"\d{9}[\dX]", digits):
        valid = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(digits)) % 11 == 0
    elif re.fullmatch(r"97[89]\d{10}", digits):
        valid = sum((3 if i % 2 else 1) * int(c) for i, c in enumerate(digits)) % 10 == 0
    else:
        raise CitationError("That doesn't look like an ISBN. It has 10 or 13 digits, like 978-0-14-143951-8.")
    if not valid:
        raise CitationError("That ISBN's last digit doesn't match the others, so there's probably a typo.")
    return digits


def lookup_isbn(isbn: str, existing: set[str]) -> Reference:
    isbn = normalize_isbn(isbn)
    params = {"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"}
    try:
        resp = requests.get(OPENLIBRARY_URL, params=params, headers=OPENLIBRARY_HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise CitationError("Could not reach Open Library. Check your connection and try again.") from exc
    except ValueError as exc:
        raise CitationError("Open Library returned an unexpected response. Please try again.") from exc
    book = data.get(f"ISBN:{isbn}") if isinstance(data, dict) else None
    if not book or not book.get("title"):
        raise CitationError(f"No book found for ISBN {isbn}. Add it under Enter manually.")
    return from_openlibrary(book, existing)


def from_openlibrary(book: dict, existing: set[str]) -> Reference:
    title = book["title"] + (f": {book['subtitle']}" if book.get("subtitle") else "")
    authors = []
    for a in book.get("authors", []):
        if name := (a.get("name") or "").strip():
            family, given = split_name(name)
            authors.append(f"{family}, {given}".strip(", "))
    year = m.group() if (m := re.search(r"\b(1[5-9]|20)\d{2}\b", book.get("publish_date", ""))) else ""
    publishers = book.get("publishers") or [{}]
    return Reference(key=make_key(authors, year, existing), kind="book", title=title, authors=authors, year=year,
                     container=(publishers[0].get("name") or "").strip())


# ---- in-text citations ------------------------------------------------------

def author_part(ref: Reference, style: str) -> str:
    fams = [split_name(a)[0] for a in ref.authors] or [ref.title[:30] or ref.key]
    joiner = " & " if style == "APA" else " and "
    if len(fams) == 1:
        return fams[0]
    if len(fams) == 2:
        return joiner.join(fams)
    return f"{fams[0]} et al."


def in_text(refs: list[Reference], style: str, numbers: dict[str, int]) -> str:
    if style == "IEEE":
        return ", ".join(f"[{numbers[r.key]}]" for r in refs)
    year = lambda r: r.year or "n.d."  # noqa: E731
    if style == "APA":
        inner = [f"{author_part(r, style)}, {year(r)}" for r in refs]
    elif style in ("Harvard", "Chicago"):
        inner = [f"{author_part(r, style)} {year(r)}" for r in refs]
    else:  # MLA
        inner = [author_part(r, style) for r in refs]
    return f"({'; '.join(inner)})"


@dataclass
class InsertResult:
    text: str
    latex: str
    used: list[Reference]  # in order of first citation
    unknown: list[str]


def insert_citations(text: str, refs: list[Reference], style: str) -> InsertResult:
    by_key = {r.key: r for r in refs}
    used: list[Reference] = []
    unknown: list[str] = []

    def keys_of(m: re.Match) -> list[str]:
        return [k.strip().lstrip("@") for k in m.group(1).split(";")]

    # First pass fixes IEEE numbering by order of first appearance.
    for m in MARKER.finditer(text):
        for k in keys_of(m):
            if k in by_key and by_key[k] not in used:
                used.append(by_key[k])
            elif k not in by_key and k not in unknown:
                unknown.append(k)
    numbers = {r.key: i for i, r in enumerate(used, 1)}

    def replace(m: re.Match) -> str:
        found = [by_key[k] for k in keys_of(m) if k in by_key]
        return in_text(found, style, numbers) if found else m.group()

    def replace_latex(m: re.Match) -> str:
        found = [k for k in keys_of(m) if k in by_key]
        return f"\\cite{{{','.join(found)}}}" if found else m.group()

    return InsertResult(MARKER.sub(replace, text), MARKER.sub(replace_latex, text), used, unknown)


# ---- reference lists --------------------------------------------------------

def _authors_ieee(ref: Reference) -> str:
    names = []
    for a in ref.authors:
        family, given = split_name(a)
        names.append(f"{initials(given)} {family}".strip())
    if len(names) > 6:
        return f"{names[0]} et al."
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1] if names else ""


def _authors_apa(ref: Reference) -> str:
    names = [f"{f}, {initials(g)}".strip(", ") for f, g in map(split_name, ref.authors)]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + ", & " + names[-1]


def _authors_mla(ref: Reference) -> str:
    if not ref.authors:
        return ""
    family, given = split_name(ref.authors[0])
    first = f"{family}, {given}".strip(", ")
    if len(ref.authors) == 1:
        return first
    if len(ref.authors) == 2:
        f2, g2 = split_name(ref.authors[1])
        return f"{first}, and {g2} {f2}".replace("  ", " ")
    return f"{first}, et al."


def _authors_harvard(ref: Reference) -> str:
    names = [f"{f}, {initials(g)}".strip(", ") for f, g in map(split_name, ref.authors)]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _authors_chicago(ref: Reference) -> str:
    """First author "Family, Given", the rest "Given Family": "Lee, Anna, and Min Park"."""
    if not ref.authors:
        return ""
    family, given = split_name(ref.authors[0])
    names = [f"{family}, {given}".strip(", ")]
    names += [f"{g} {f}".strip() for f, g in map(split_name, ref.authors[1:])]
    if len(names) > 10:  # Chicago lists up to ten, otherwise the first seven and "et al."
        return ", ".join(names[:7]) + ", et al."
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + ", and " + names[-1]


def _link(ref: Reference) -> str:
    return f"https://doi.org/{ref.doi}" if ref.doi else ref.url


def format_entry(ref: Reference, style: str) -> str:
    """One reference-list entry, in Markdown (titles of books and journals in italics)."""
    y = ref.year or "n.d."
    link = _link(ref)
    if style == "IEEE":
        a = _authors_ieee(ref)
        lead = f"{a}, " if a else ""
        if ref.kind == "book":
            out = f"{lead}*{ref.title}*. {ref.container + ', ' if ref.container else ''}{ref.year}."
        elif ref.kind == "web":
            out = f'{lead}"{ref.title}," {ref.container + ", " if ref.container else ""}{ref.year + ". " if ref.year else ""}[Online]. Available: {ref.url}'
        else:
            bits = [f"*{ref.container}*"] if ref.container else []
            bits += [f"vol. {ref.volume}"] if ref.volume else []
            bits += [f"no. {ref.issue}"] if ref.issue else []
            bits += [f"pp. {ref.pages}"] if ref.pages else []
            bits += [ref.year] if ref.year else []
            out = f'{lead}"{ref.title}," {", ".join(bits)}'
            out += f", doi: {ref.doi}." if ref.doi else "."
        return out.strip()

    if style == "APA":
        a = _authors_apa(ref)
        head = f"{a} ({y}). " if a else f"{ref.title}. ({y}). "
        title = "" if not a else (f"*{ref.title}*. " if ref.kind != "article" else f"{ref.title}. ")
        if ref.kind == "article":
            src = f"*{ref.container}*" if ref.container else ""
            src += f", *{ref.volume}*" if ref.volume else ""
            src += f"({ref.issue})" if ref.issue else ""
            src += f", {ref.pages}" if ref.pages else ""
            src = src + ". " if src else ""
        else:
            src = f"{ref.container.rstrip('.')}. " if ref.container else ""
        return f"{head}{title}{src}{link}".strip()

    if style == "MLA":
        a = _authors_mla(ref)
        lead = f"{a}. " if a else ""
        if ref.kind == "book":
            return f"{lead}*{ref.title}*. {ref.container + ', ' if ref.container else ''}{ref.year}.".strip()
        bits = [f"*{ref.container}*"] if ref.container else []
        bits += [f"vol. {ref.volume}"] if ref.volume else []
        bits += [f"no. {ref.issue}"] if ref.issue else []
        bits += [ref.year] if ref.year else []
        bits += [f"pp. {ref.pages}"] if ref.pages else []
        bits += [link] if link else []
        return f'{lead}"{ref.title}." {", ".join(bits)}.'.strip()

    if style == "Chicago":
        a = _authors_chicago(ref)
        title = f"*{ref.title}*. " if ref.kind == "book" else f"“{ref.title}.” "
        if ref.kind == "article":
            src = f"*{ref.container}*" if ref.container else ""
            src += f" {ref.volume}" if ref.volume else ""
            src += f" ({ref.issue})" if ref.issue else ""
            src += f": {ref.pages}" if ref.pages else ""
            src = f"{src.strip()}. " if src else ""
        else:
            src = f"{ref.container.rstrip('.')}. " if ref.container else ""
        # with no author, the title takes the author's place in front of the year
        year = f"{y} " if y.endswith(".") else f"{y}. "  # "n.d." already ends in a full stop
        parts = [f"{a.rstrip('.')}. ", year, title] if a else [title, year]
        return ("".join(parts) + src + (f"{link}." if link else "")).strip()

    # Harvard
    a = _authors_harvard(ref)
    head = f"{a} ({y}) " if a else f"*{ref.title}* ({y}) "
    if ref.kind == "book":
        body = (f"*{ref.title}*. " if a else "") + (f"{ref.container}." if ref.container else "")
    else:
        body = (f"'{ref.title}', " if a else "") + (f"*{ref.container}*" if ref.container else "")
        body += f", {ref.volume}" if ref.volume else ""
        body += f"({ref.issue})" if ref.issue else ""
        body += f", pp. {ref.pages}" if ref.pages else ""
        body += "."
    if ref.kind == "web" and ref.url:
        body += f" Available at: {ref.url}"
    elif ref.doi:
        body += f" doi: {ref.doi}."
    return f"{head}{body}".strip()


def sort_for_style(refs: list[Reference], style: str) -> list[Reference]:
    """IEEE keeps citation order; the author-date styles sort alphabetically."""
    if style == "IEEE":
        return list(refs)
    return sorted(refs, key=lambda r: (split_name(r.authors[0])[0].lower() if r.authors else r.title.lower(), r.year))


def reference_list(refs: list[Reference], style: str) -> list[str]:
    ordered = sort_for_style(refs, style)
    if style == "IEEE":
        return [f"[{i}] {format_entry(r, style)}" for i, r in enumerate(ordered, 1)]
    return [format_entry(r, style) for r in ordered]


# ---- export / import --------------------------------------------------------

def _bib_escape(value: str) -> str:
    return re.sub(r"(?<!\\)([&%#$_])", r"\\\1", value)


def to_bibtex(refs: list[Reference]) -> str:
    entries = []
    for r in refs:
        kind = {"article": "article", "book": "book", "web": "misc"}[r.kind]
        container_field = {"article": "journal", "book": "publisher", "web": "howpublished"}[r.kind]
        fields = [
            ("author", " and ".join(f"{f}, {g}".strip(", ") for f, g in map(split_name, r.authors))),
            ("title", f"{{{_bib_escape(r.title)}}}"),
            (container_field, _bib_escape(r.container)),
            ("year", r.year),
            ("volume", r.volume),
            ("number", r.issue),
            ("pages", r.pages.replace("-", "--") if "--" not in r.pages else r.pages),
            ("doi", r.doi),
            ("url", r.url),
        ]
        body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields if v)
        entries.append(f"@{kind}{{{r.key},\n{body}\n}}")
    return "\n\n".join(entries) + ("\n" if entries else "")


CSL_TYPES = {"article": "article-journal", "book": "book", "web": "webpage"}


def to_csl_json(refs: list[Reference]) -> str:
    items = []
    for r in refs:
        item = {
            "id": r.key,
            "type": CSL_TYPES[r.kind],
            "title": r.title,
            "author": [{"family": f, "given": g} for f, g in map(split_name, r.authors)],
        }
        if r.year:
            item["issued"] = {"date-parts": [[int(r.year)] if r.year.isdigit() else [r.year]]}
        if r.container:
            item["publisher" if r.kind == "book" else "container-title"] = r.container
        for key, value in (("volume", r.volume), ("issue", r.issue), ("page", r.pages), ("DOI", r.doi), ("URL", r.url)):
            if value:
                item[key] = value
        items.append(item)
    return json.dumps(items, indent=2, ensure_ascii=False)


def from_csl_json(data: str, existing: set[str]) -> list[Reference]:
    try:
        items = json.loads(data)
    except ValueError as exc:
        raise CitationError("That file isn't valid JSON.") from exc
    if not isinstance(items, list):
        raise CitationError("Expected a JSON list of references (CSL-JSON).")
    kinds = {v: k for k, v in CSL_TYPES.items()}
    refs, keys = [], set(existing)
    for item in items:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        authors = [
            f"{a.get('family', '')}, {a.get('given', '')}".strip(", ") or a.get("literal", "")
            for a in item.get("author", [])
            if isinstance(a, dict)
        ]
        parts = (item.get("issued") or {}).get("date-parts") or [[""]]
        year = str(parts[0][0]) if parts and parts[0] else ""
        kind = kinds.get(item.get("type"), "article")
        key = str(item.get("id") or "")
        if not re.fullmatch(r"[\w:-]+", key) or key in keys:
            key = make_key(authors, year, keys)
        keys.add(key)
        refs.append(
            Reference(
                key=key,
                kind=kind,
                title=str(item["title"]),
                authors=[a for a in authors if a],
                year=year,
                container=str(item.get("publisher" if kind == "book" else "container-title", "")),
                volume=str(item.get("volume", "")),
                issue=str(item.get("issue", "")),
                pages=str(item.get("page", "")),
                doi=str(item.get("DOI", "")),
                url=str(item.get("URL", "")),
            )
        )
    if not refs:
        raise CitationError("No references with a title were found in that file.")
    return refs


def to_dict(ref: Reference) -> dict:
    return asdict(ref)
