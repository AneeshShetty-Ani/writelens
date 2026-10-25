"""Cite a web page from its URL: fetch the page and read the title, authors, date and site name from its
metadata (Highwire citation_* tags, Open Graph, JSON-LD), the same tags reference managers like Zotero use."""

import ipaddress
import json
import re
import socket
import urllib.parse
from html.parser import HTMLParser

import requests

from citations import CitationError, Reference, make_key

TIMEOUT = 10
MAX_BYTES = 2_000_000
MAX_REDIRECTS = 4
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WriteLens citation fetcher)", "Accept": "text/html,*/*;q=0.5"}
YEAR = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")
HIDDEN_TAGS = {"script", "style", "noscript", "template", "svg"}
MAX_TEXT = 20_000


class MetaParser(HTMLParser):
    """Collects <meta> name/property -> contents, the <title> text, JSON-LD blocks, and the visible text
    (for finding a byline when the metadata has no author or date)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, list[str]] = {}
        self.title = ""
        self.json_ld: list[str] = []
        self.text: list[str] = []
        self._in = ""  # "title" or "ld" while inside those tags
        self._hidden = 0  # depth inside <script>, <style> and the like

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            name = (a.get("name") or a.get("property") or a.get("itemprop") or "").strip().lower()
            if name and a.get("content", "").strip():
                self.meta.setdefault(name, []).append(a["content"].strip())
        elif tag == "title" and not self.title:
            self._in = "title"
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in = "ld"
            self.json_ld.append("")
        if tag in HIDDEN_TAGS:
            self._hidden += 1

    def handle_endtag(self, tag):
        if tag in ("title", "script"):
            self._in = ""
        if tag in HIDDEN_TAGS and self._hidden:
            self._hidden -= 1

    def handle_data(self, data):
        if self._in == "title":
            self.title += data
        elif self._in == "ld":
            self.json_ld[-1] += data
        elif not self._hidden and data.strip() and sum(map(len, self.text)) < MAX_TEXT:
            self.text.append(" ".join(data.split()))


# ---- fetching ---------------------------------------------------------------

def check_url(url: str) -> str:
    """Only public http(s) addresses: the app may run on a server, and must not be usable to reach
    that server's own or private network."""
    url = url.strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise CitationError("Enter a web address starting with http:// or https://.")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    except (socket.gaierror, UnicodeError) as exc:
        raise CitationError(f"Couldn't find the website {parts.hostname}.") from exc
    for info in infos:
        if not ipaddress.ip_address(info[4][0].split("%")[0]).is_global:
            raise CitationError("That address points to a private or local network, so it can't be fetched.")
    return url


def connected_to_public_ip(resp: requests.Response) -> bool:
    """The IP the response came from (read before downloading the body). Unknown counts as not public."""
    try:
        peer = resp.raw.connection.sock.getpeername()[0]
        return ipaddress.ip_address(peer.split("%")[0]).is_global
    except (AttributeError, OSError, ValueError, TypeError):
        return False


def fetch_html(url: str) -> tuple[str, str]:
    """Return (final url, html), checking every redirect hop."""
    for _ in range(MAX_REDIRECTS + 1):
        url = check_url(url)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=False, stream=True)
        except requests.RequestException as exc:
            raise CitationError("Couldn't reach that website. Check the address and your connection.") from exc
        if resp.is_redirect and resp.headers.get("location"):
            # nothing is read from a redirect but its Location, and the next hop is checked again
            url = urllib.parse.urljoin(url, resp.headers["location"])
            resp.close()
            continue
        # check_url looked the name up once, but requests looks it up again; a hostile DNS server
        # could answer with a private address the second time. Check where we actually connected
        # before reading the page.
        if not connected_to_public_ip(resp):
            resp.close()
            raise CitationError("That address points to a private or local network, so it can't be fetched.")
        if resp.status_code >= 400:
            raise CitationError(f"The website answered with error {resp.status_code}.")
        if "html" not in resp.headers.get("content-type", "html").lower():
            raise CitationError("That address isn't a web page (it may be a PDF or image). Add it under Enter manually.")
        body = b""
        for chunk in resp.iter_content(65536):
            body += chunk
            if len(body) >= MAX_BYTES:
                break
        resp.close()
        # requests assumes ISO-8859-1 when no charset is given, but nearly every page today is UTF-8
        charset = resp.encoding if "charset" in resp.headers.get("content-type", "").lower() else "utf-8"
        try:
            return url, body.decode(charset or "utf-8", errors="replace")
        except LookupError:  # an unknown charset name
            return url, body.decode("utf-8", errors="replace")
    raise CitationError("Too many redirects.")


# ---- reading the metadata -----------------------------------------------------

def walk_json_ld(node):
    """Yield every dict in a JSON-LD document (it may be a list or use @graph)."""
    if isinstance(node, list):
        for item in node:
            yield from walk_json_ld(item)
    elif isinstance(node, dict):
        yield node
        yield from walk_json_ld(node.get("@graph", []))


def name_of(value, people_only: bool = False) -> list[str]:
    if isinstance(value, list):
        return [n for v in value for n in name_of(v, people_only)]
    if isinstance(value, dict):
        # "Contributors to Wikimedia projects" is an Organization, not an author to cite by name
        if people_only and "Organization" in str(value.get("@type", "")):
            return []
        return name_of(value.get("name", ""))
    return [str(value)] if value else []


def split_title(title: str, hostname: str) -> tuple[str, str]:
    """'Photosynthesis - Wikipedia' on wikipedia.org -> ('Photosynthesis', 'Wikipedia')."""
    for sep in (" | ", " - ", " – ", " — "):
        if sep in title:
            head, tail = title.rsplit(sep, 1)
            word = re.sub(r"[^a-z0-9]", "", tail.split()[0].lower()) if tail.split() else ""
            if len(word) >= 3 and word in hostname.replace(".", ""):
                return head.strip(), tail.strip()
    return title, ""


def clean_author(name: str) -> str:
    name = re.sub(r"^\s*by\s+", "", name.strip(), flags=re.IGNORECASE)
    return "" if not name or name.startswith(("http", "@")) or len(name) > 80 else name


def extract(html: str, url: str) -> dict:
    p = MetaParser()
    p.feed(html)
    meta = lambda *names: next((p.meta[n] for n in names if n in p.meta), [])  # noqa: E731

    ld = {}
    for block in p.json_ld:
        try:
            for node in walk_json_ld(json.loads(block)):
                if any(k in node for k in ("headline", "datePublished", "author")):
                    ld = node
                    break
        except ValueError:
            continue
        if ld:
            break

    hostname = (urllib.parse.urlsplit(url).hostname or "").lower()
    title = (meta("citation_title", "og:title", "twitter:title", "dc.title") or [str(ld.get("headline") or "")])[0]
    title = " ".join((title or p.title).split())
    title, title_site = split_title(title, hostname)

    # the page's own name for itself first; a "Title - Site" suffix beats the publisher's company name
    site = next(s for s in (*meta("og:site_name", "citation_journal_title"), title_site,
                            *name_of(ld.get("publisher")), re.sub(r"^www\.", "", hostname)) if s)
    for sep in (" | ", " - ", " – ", " — "):
        if title.endswith(sep + site):
            title = title[: -len(sep + site)]

    raw_authors = (meta("citation_author", "dc.creator") or name_of(ld.get("author"), people_only=True)
                   or meta("author", "article:author", "parsely-author"))
    authors = []
    for a in raw_authors:
        for part in re.split(r"\s+and\s+|\s*&\s*", a):
            if (name := clean_author(part)) and name not in authors and name != site:
                authors.append(name)

    date = (meta("citation_publication_date", "citation_date", "article:published_time", "dc.date", "date", "pubdate")
            or [str(ld.get("datePublished") or "")])[0]
    year = m.group(1) if (m := YEAR.search(date)) else ""

    return {"title": title, "authors": authors, "year": year, "site": site, "url": url, "text": "\n".join(p.text)}


def read_page(url: str) -> dict:
    """The page's details (see extract), with the address to cite."""
    final_url, html = fetch_html(url)
    info = extract(html, final_url)
    # Redirects to the same page often add tracking or cookie-check queries; cite the address given.
    given = check_url(url)
    if urllib.parse.urlsplit(given).path.rstrip("/") == urllib.parse.urlsplit(final_url).path.rstrip("/"):
        info["url"] = given
    if not info["title"]:
        raise CitationError("Couldn't find a title on that page. Add it under Enter manually.")
    return info


def page_reference(info: dict, existing: set[str]) -> Reference:
    # no author: key on the whole site name ("Site," keeps make_key from taking only its last word)
    return Reference(
        key=make_key(info["authors"] or [info["site"] + ","], info["year"], existing), kind="web", title=info["title"],
        authors=info["authors"], year=info["year"], container=info["site"], url=info["url"],
    )


def lookup_url(url: str, existing: set[str]) -> Reference:
    return page_reference(read_page(url), existing)
