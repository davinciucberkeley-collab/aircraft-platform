"""Citation check: does a cited URL point at the page the citation names?

Citations are read from knowledge/ (markdown frontmatter and markdown links) and
standards/ (https URLs inside YAML `source:` strings). Only citations on lines
added relative to a base ref are checked, so old entries are not re-fetched.
"""
from __future__ import annotations

import html
import re
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, NamedTuple

import yaml

from .design import REPO_ROOT

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0 Safari/537.36")
TIMEOUT_S = 15
MAX_BYTES = 2_000_000

URL_RE = re.compile(r"https://[^\s\"'<>()\[\]]+")
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\((https://[^)\s]+)\)")
FM_KEY_RE = re.compile(r"^(source_url|url|related_video):\s*(.*)$")
FM_TITLE_RE = re.compile(r"^title:\s*(.*)$")
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

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

# Words that name a kind of source rather than the thing cited. Not enough on their own to
# count as the "distinctive" token of a citation (e.g. "MIT MS thesis" must not match a thesis).
GENERIC_CITE = {"thesis", "paper", "report", "article", "study", "journal", "review", "university",
                "wikipedia", "video", "blog", "thread", "document", "guide", "manual", "datasheet",
                "data", "sheet", "technical", "specification", "standard", "version"}

YOUTUBE_HOSTS = ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be")


class Citation(NamedTuple):
    url: str
    claimed_text: str
    path: str
    line: int


@dataclass
class CheckResult:
    citation: Citation
    status: str
    message: str
    page_title: str | None


FetchFn = Callable[[str], "tuple[str, str]"]


# ---------------------------------------------------------------- extraction

def _clean(s: str) -> str:
    s = s.strip().strip("\"'").strip()
    return re.sub(r"\s+", " ", s)


def _knowledge_citations(text: str, path: str) -> list[Citation]:
    out: list[Citation] = []
    lines = text.splitlines()
    in_fm = bool(lines) and lines[0].strip() == "---"
    fm_end = None
    title = ""
    fm_urls: list[tuple[str, int]] = []
    if in_fm:
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
        root = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError:
        return []
    out: list[Citation] = []

    def walk(node):
        if isinstance(node, yaml.MappingNode):
            for k, v in node.value:
                if (isinstance(k, yaml.ScalarNode) and k.value == "source"
                        and isinstance(v, yaml.ScalarNode) and isinstance(v.value, str)):
                    urls = [u.rstrip(".,;:") for u in URL_RE.findall(v.value)]
                    if urls:
                        claimed = URL_RE.sub(" ", v.value).replace("()", " ")
                        claimed = re.sub(r"\s+", " ", claimed).strip()
                        for u in urls:
                            out.append(Citation(u, claimed, path, v.start_mark.line + 1))
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
    """{repo-relative path: line numbers (new file) added by the diff}. Expects --unified=0."""
    added: dict[str, set[int]] = {}
    current: str | None = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            current = target[2:] if target.startswith("b/") else None
            if current is not None:
                added.setdefault(current, set())
        elif line.startswith("@@") and current is not None:
            m = HUNK_RE.match(line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2)) if m.group(2) is not None else 1
                added[current].update(range(start, start + count))
    return {k: v for k, v in added.items() if v}


def added_citations(base_ref: str, repo_root: Path = REPO_ROOT) -> list[Citation]:
    """Citations on lines added under knowledge/ or standards/ relative to base_ref."""
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

def default_fetch(url: str) -> tuple[str, str]:
    """(content type, decoded body). Raises on network errors and timeouts."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # follows redirects
        ctype = resp.headers.get("Content-Type", "") or ""
        charset = resp.headers.get_content_charset() or "utf-8"
        raw = resp.read(MAX_BYTES)
    return ctype, raw.decode(charset, errors="replace")


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


def check_detail(citation: Citation, fetch: FetchFn = default_fetch) -> CheckResult:
    def res(status: str, message: str, title: str | None = None) -> CheckResult:
        return CheckResult(citation, status, message, title)

    host = re.sub(r"^https?://", "", citation.url).split("/")[0].lower()
    if host in YOUTUBE_HOSTS:
        return res(WARN, "not checkable: video host")
    if not citation.claimed_text.strip():
        return res(WARN, "could not verify: no claim text to compare")
    try:
        ctype, body = fetch(citation.url)
    except Exception as e:  # noqa: BLE001 - any fetch problem is a WARN, not a FAIL
        return res(WARN, f"could not verify: {type(e).__name__}: {e}")
    if ctype and not re.search(r"html|xml", ctype, flags=re.I):
        return res(WARN, f"could not verify: non-HTML content ({ctype})")

    title = page_title(body)
    claimed_sig = _significant(citation.claimed_text)
    title_shared = claimed_sig & _significant(title or "")
    if title_shared:
        return res(PASS, f"title shares: {', '.join(sorted(title_shared))}", title)

    distinctive = claimed_sig - GENERIC_CITE
    body_hits = distinctive & _tokens(_strip_tags(body))
    if body_hits:
        return res(PASS, f"name found in page text: {', '.join(sorted(body_hits))}", title)

    shown = title if title else "(no title)"
    return res(FAIL, f"cited as '{citation.claimed_text}' but page is '{shown}'", title)


def check(citation: Citation, fetch: FetchFn = default_fetch) -> tuple[str, str]:
    r = check_detail(citation, fetch)
    return r.status, r.message
