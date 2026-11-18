"""Citation check: does a cited URL point at the page the citation names?

Citations are read from knowledge/ (markdown frontmatter and markdown links) and
standards/ (https URLs in YAML `source:`, `source_url:` and `url:` values). Only citations on
lines added relative to a base ref are checked, so old entries are not re-fetched.
"""
from __future__ import annotations

import html
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, NamedTuple
from urllib.parse import urlsplit

import yaml

from .design import REPO_ROOT

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0 Safari/537.36")
TIMEOUT_S = 15
MAX_BYTES = 2_000_000
HEAD_CHARS = 5000  # how much of the page text counts as "the page" for a name match

URL_RE = re.compile(r"https://[^\s\"'<>()\[\]]+")
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\((https://[^)\s]+)\)")
FM_KEY_RE = re.compile(r"^\s*[\"']?(source_url|url|related_video)[\"']?\s*:\s*(.*)$")
FM_TITLE_RE = re.compile(r"^\s*[\"']?title[\"']?\s*:\s*(.*)$")
YAML_URL_KEYS = ("source", "source_url", "url")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

STOPWORDS = set("""
about above after again against also among and any are aren because been before being below between
both but can could did does doing down during each few for from further had has have having here hers
herself him himself his how into its itself just more most nor not now off once only other ought our
ours out over own same she should some such than that the their theirs them themselves then there these
they this those through too under until very was were what when where which while who whom why will
with would your yours yourself checked retrieved accessed
""".split())

# Very common web-page words: they say nothing about which page this is.
WEB_WORDS = {"home", "homepage", "page", "site", "website", "welcome", "official", "index", "menu",
             "search", "login", "untitled", "online", "click", "read", "more", "contact"}

# Words that name a kind of source or a common topic rather than the thing cited. They never count
# as a shared title word or as the "distinctive" token of a citation (e.g. "MIT MS thesis" must
# not match a thesis; "APC propeller performance data" must not match "Data privacy policy").
GENERIC_CITE = {"thesis", "paper", "report", "article", "study", "journal", "review", "university",
                "wikipedia", "video", "blog", "thread", "document", "guide", "manual", "datasheet",
                "data", "sheet", "technical", "specification", "standard", "version",
                "privacy", "policy", "repository", "performance", "information", "download",
                "downloads", "archive", "collection", "database", "results", "project", "projects",
                "portal", "forum", "notes", "library", "resources", "catalog", "news"}

YOUTUBE_HOSTS = ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be")
NOT_VERIFIABLE_4XX = (401, 403, 429)


class Citation(NamedTuple):
    url: str
    claimed_text: str
    path: str
    line: int


class Response(NamedTuple):
    status: int
    ctype: str
    body: str
    final_url: str  # the URL after any redirects


@dataclass
class CheckResult:
    citation: Citation
    status: str
    message: str
    page_title: str | None


FetchFn = Callable[[str], Response]


# ---------------------------------------------------------------- extraction

def _clean(s: str) -> str:
    s = s.strip().strip("\"'").strip()
    return re.sub(r"\s+", " ", s)


def _normalise(text: str) -> str:
    """Drop a BOM and make line endings plain \\n so line numbers and regexes behave."""
    return text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")


def _knowledge_citations(text: str, path: str) -> list[Citation]:
    out: list[Citation] = []
    lines = _normalise(text).split("\n")
    fm_end = None
    title = ""
    fm_urls: list[tuple[str, int]] = []
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm_end = i
                break
        for i in range(1, fm_end if fm_end is not None else len(lines)):
            m = FM_TITLE_RE.match(lines[i])
            if m:
                title = _clean(m.group(1))
            m = FM_KEY_RE.match(lines[i])
            if m:
                for u in URL_RE.findall(m.group(2)):
                    fm_urls.append((u.rstrip(".,;:"), i + 1))
    for url, lineno in fm_urls:
        out.append(Citation(url, title, path, lineno))
    for i, line in enumerate(lines, start=1):
        for m in MD_LINK_RE.finditer(line):
            out.append(Citation(m.group(2).rstrip(".,;:"), _clean(m.group(1)), path, i))
    return out


def _yaml_source_citations(text: str, path: str) -> list[Citation]:
    try:
        root = yaml.compose(_normalise(text), Loader=yaml.SafeLoader)
    except yaml.YAMLError:
        return []
    out: list[Citation] = []

    def scalar(node):
        return node.value if isinstance(node, yaml.ScalarNode) and isinstance(node.value, str) else None

    def walk(node):
        if isinstance(node, yaml.MappingNode):
            sibling_name = ""
            for k, v in node.value:
                if scalar(k) == "name" and scalar(v):
                    sibling_name = _clean(scalar(v))
            for k, v in node.value:
                key, value = scalar(k), scalar(v)
                if key in YAML_URL_KEYS and value is not None:
                    if key == "source":
                        claimed = URL_RE.sub(" ", value).replace("()", " ")
                        claimed = re.sub(r"\s+", " ", claimed).strip()
                    else:
                        claimed = sibling_name
                    for m in URL_RE.finditer(value):
                        # line of the URL itself, for multi-line scalars
                        line = v.start_mark.line + 1 + value[:m.start()].count("\n")
                        out.append(Citation(m.group().rstrip(".,;:"), claimed, path, line))
                walk(v)
        elif isinstance(node, yaml.SequenceNode):
            for item in node.value:
                walk(item)

    if root is not None:
        walk(root)
    return out


def extract_citations(text: str, path: str) -> list[Citation]:
    """Citations in one file. `path` is repo-relative and decides which rules apply."""
    p = Path(path).as_posix()
    if p.startswith("knowledge/") and p.endswith(".md"):
        return _knowledge_citations(text, p)
    if p.startswith("standards/") and p.endswith((".yaml", ".yml")):
        return _yaml_source_citations(text, p)
    return []


# ---------------------------------------------------------------- git diff

def _git(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def _added_lines(diff: str) -> dict[str, set[int]]:
    """{repo-relative path: new-file line numbers that the diff adds or rewrites}.

    Expects --unified=0. Hunk bodies are read by their line counts, so an added content line
    that happens to start with "+++ " or "--- " is still treated as a + line, not a header.
    """
    added: dict[str, set[int]] = {}
    current: str | None = None
    old_left = new_left = 0
    new_no = 0
    for line in diff.splitlines():
        if old_left > 0 or new_left > 0:
            if line.startswith("\\"):
                continue  # "\ No newline at end of file"
            if line.startswith("+"):
                if current is not None:
                    added.setdefault(current, set()).add(new_no)
                new_no += 1
                new_left -= 1
            elif line.startswith("-"):
                old_left -= 1
            else:
                old_left = new_left = 0
            continue
        if line.startswith("+++ "):
            target = line[4:].strip()
            current = target[2:] if target.startswith("b/") else None
        elif line.startswith("@@"):
            m = HUNK_RE.match(line)
            if m:
                old_left = int(m.group(2)) if m.group(2) is not None else 1
                new_left = int(m.group(4)) if m.group(4) is not None else 1
                new_no = int(m.group(3))
                if current is not None:
                    added.setdefault(current, set())
    return {k: v for k, v in added.items() if v}


def added_citations(base_ref: str, repo_root: Path = REPO_ROOT) -> list[Citation]:
    """Citations on lines added or rewritten under knowledge/ or standards/ relative to base_ref."""
    diff = _git(repo_root, "diff", "--no-color", "--no-ext-diff", "--unified=0", base_ref,
                "--", "knowledge", "standards")
    out: list[Citation] = []
    for path, lines in sorted(_added_lines(diff).items()):
        full = Path(repo_root) / path
        if not full.is_file():
            continue
        text = full.read_text(encoding="utf-8", errors="replace")
        out += [c for c in extract_citations(text, path) if c.line in lines]
    return out


# ---------------------------------------------------------------- checking

def default_fetch(url: str) -> Response:
    """Status, content type, decoded body and final URL. Raises on network errors and timeouts."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT_S)  # follows redirects
    except urllib.error.HTTPError as e:
        try:
            raw = e.read(MAX_BYTES)
        except Exception:  # noqa: BLE001 - the body of an error page is optional
            raw = b""
        return Response(e.code, e.headers.get("Content-Type", "") or "",
                        raw.decode("utf-8", errors="replace"), url)
    with resp:
        ctype = resp.headers.get("Content-Type", "") or ""
        charset = resp.headers.get_content_charset() or "utf-8"
        raw = resp.read(MAX_BYTES)
        final = resp.geturl() or url
        status = resp.getcode() or 200
    return Response(status, ctype, raw.decode(charset, errors="replace"), final)


def _strip_tags(s: str) -> str:
    s = re.sub(r"<(script|style)\b.*?</\1\s*>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def page_title(body: str) -> str | None:
    """<title>, else og:title, else the first <h1>."""
    m = re.search(r"<title[^>]*>(.*?)</title>", body, flags=re.S | re.I)
    if m and _strip_tags(m.group(1)):
        return _strip_tags(m.group(1))
    for tag in re.findall(r"<meta\b[^>]*>", body, flags=re.I):
        attrs = dict((k.lower(), v) for k, v in re.findall(r"([\w:-]+)\s*=\s*[\"']([^\"']*)[\"']", tag))
        if attrs.get("property", attrs.get("name", "")).lower() == "og:title" and attrs.get("content"):
            return _strip_tags(attrs["content"])
    m = re.search(r"<h1[^>]*>(.*?)</h1>", body, flags=re.S | re.I)
    if m and _strip_tags(m.group(1)):
        return _strip_tags(m.group(1))
    return None


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{4,}", text.lower()))


def _significant(text: str) -> set[str]:
    return _tokens(text) - STOPWORDS - WEB_WORDS


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _norm_url(url: str) -> tuple[str, str, str, str]:
    s = urlsplit(url)
    return (s.scheme.lower(), (s.hostname or "").lower(), s.path.rstrip("/"), s.query)


def _match(claimed: str, title: str | None, body: str) -> str | None:
    """Why the page matches the claim, or None. Generic words never count."""
    distinct_claim = _significant(claimed) - GENERIC_CITE
    shared = distinct_claim & _significant(title or "")
    if len(shared) >= 2:
        return f"title shares: {', '.join(sorted(shared))}"
    distinctive = {t for t in distinct_claim if len(t) >= 5}
    found = distinctive & (_tokens(title or "") | _tokens(_strip_tags(body)[:HEAD_CHARS]))
    if found:
        return f"name found: {', '.join(sorted(found))}"
    return None


def check_detail(citation: Citation, fetch: FetchFn = default_fetch) -> CheckResult:
    def res(status: str, message: str, title: str | None = None) -> CheckResult:
        return CheckResult(citation, status, message, title)

    host = _host(citation.url)
    if host in YOUTUBE_HOSTS:
        return res(WARN, "not checkable: video host")
    if not citation.claimed_text.strip():
        return res(WARN, "could not verify: no claim text to compare")
    try:
        resp = fetch(citation.url)
    except Exception as e:  # noqa: BLE001 - any fetch problem is a WARN, not a FAIL
        return res(WARN, f"could not verify: {type(e).__name__}: {e}")
    if resp.status >= 400:
        if resp.status in NOT_VERIFIABLE_4XX or resp.status >= 500:
            return res(WARN, f"could not verify: HTTP {resp.status}")
        return res(FAIL, f"link is dead (HTTP {resp.status})")
    if resp.ctype and not re.search(r"html|xml", resp.ctype, flags=re.I):
        return res(WARN, f"could not verify: non-HTML content ({resp.ctype})")

    title = page_title(resp.body)
    matched = _match(citation.claimed_text, title, resp.body)
    final = resp.final_url or citation.url
    if _norm_url(final) != _norm_url(citation.url):
        if urlsplit(final).path.rstrip("/") == "":
            return res(FAIL, f"redirected to {final}", title)
        if _host(final) != host and matched is None:
            return res(FAIL, f"redirected to {final}", title)
    if matched is not None:
        return res(PASS, matched, title)

    shown = title if title else "(no title)"
    return res(FAIL, f"cited as '{citation.claimed_text}' but page is '{shown}'", title)


def check(citation: Citation, fetch: FetchFn = default_fetch) -> tuple[str, str]:
    r = check_detail(citation, fetch)
    return r.status, r.message
