"""Citation check. No network: every test injects a fake fetch."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aircraft_platform.citations import (Citation, Response, added_citations, check, check_detail,
                                         extract_citations)

LAW_REVIEW_URL = "https://dspace.mit.edu/handle/1721.1/130873"
LAW_REVIEW_TITLE = ("Changes and Opportunities in the Environment for Technology Bargaining | "
                    "Notre Dame Law Review")


def page(title: str, body: str = "") -> str:
    return f"<html><head><title>{title}</title></head><body>{body}</body></html>"


def fake_returning(html: str, *, status: int = 200, final_url: str | None = None,
                   ctype: str = "text/html; charset=utf-8"):
    """Fake fetch. The response's final_url is the requested URL unless a test says otherwise."""
    calls = []

    def fetch(url):
        calls.append(url)
        return Response(status, ctype, html, final_url or url)
    fetch.calls = calls
    return fetch


def cite(url: str, claimed: str) -> Citation:
    return Citation(url, claimed, "standards/design-standards.yaml", 1)


# ---------------------------------------------------------------- matching and fetch errors

def test_law_review_case_fails():
    c = cite(LAW_REVIEW_URL, "AeroSandbox (Sharpe 2021, MIT MS thesis)")
    status, msg = check(c, fetch=fake_returning(page(LAW_REVIEW_TITLE, "Technology bargaining.")))
    assert status == "FAIL"
    assert "cited as 'AeroSandbox (Sharpe 2021, MIT MS thesis)'" in msg
    assert "Notre Dame Law Review" in msg


def test_matching_title_passes():
    c = cite("https://flitetest.com/articles/bixler", "Bixler Scratch Build (Hot Wire Foam Cutter)")
    status, _ = check(c, fetch=fake_returning(page("Bixler Scratch Build - Flite Test")))
    assert status == "PASS"


def test_product_name_in_body_passes():
    c = cite("https://example.org/aero", "AeroSandbox (Sharpe 2021)")
    body = "<h1>Home</h1><p>AeroSandbox is an aircraft design toolkit.</p>"
    status, _ = check(c, fetch=fake_returning(page("Home | Example", body)))
    assert status == "PASS"


def test_name_past_first_5000_chars_of_body_does_not_pass():
    c = cite("https://example.org/aero", "AeroSandbox (Sharpe 2021)")
    body = "<p>" + ("filler words " * 800) + "AeroSandbox</p>"
    status, _ = check(c, fetch=fake_returning(page("Home | Example", body)))
    assert status == "FAIL"


def test_timeout_warns():
    def fetch(url):
        raise TimeoutError("timed out")
    status, msg = check(cite("https://example.org/slow", "Some Title Here"), fetch=fetch)
    assert status == "WARN"
    assert "could not verify" in msg


def test_youtube_warns_without_fetching():
    fake = fake_returning(page("Anything"))
    status, msg = check(cite("https://youtu.be/abc123", "Some video"), fetch=fake)
    assert status == "WARN"
    assert "not checkable" in msg
    assert fake.calls == []


def test_non_html_warns():
    def fetch(url):
        return Response(200, "application/pdf", "%PDF-1.4", url)
    status, _ = check(cite("https://example.org/a.pdf", "Some Report Title"), fetch=fetch)
    assert status == "WARN"


# Round 13 K3: an invented URL that returns 404 must FAIL.
@pytest.mark.parametrize("code", [404, 410, 400, 418])
def test_dead_link_fails(code):
    c = cite("https://example.org/invented-page", "Bixler Scratch Build")
    status, msg = check(c, fetch=fake_returning("Not found", status=code))
    assert status == "FAIL"
    assert msg == f"link is dead (HTTP {code})"


@pytest.mark.parametrize("code", [401, 403, 429, 500, 503])
def test_unverifiable_status_warns(code):
    c = cite("https://example.org/page", "Bixler Scratch Build")
    status, msg = check(c, fetch=fake_returning("Blocked", status=code))
    assert status == "WARN"
    assert msg == f"could not verify: HTTP {code}"


# Round 13 K4: titles that share only a generic word must not PASS.
def test_shared_generic_thesis_word_fails():
    c = cite("https://example.org/selig", "Selig 1997 airfoil thesis")
    body = "Medieval poetry thesis."
    status, msg = check(c, fetch=fake_returning(page("Thesis repository: Medieval poetry thesis", body)))
    assert status == "FAIL"
    assert "title shares" not in msg


def test_shared_generic_data_word_fails():
    c = cite("https://example.org/apc", "APC propeller performance data")
    status, _ = check(c, fetch=fake_returning(page("Data privacy policy", "We respect your privacy.")))
    assert status == "FAIL"


def test_two_shared_significant_words_pass():
    c = cite("https://example.org/selig", "Selig airfoil thesis")
    status, msg = check(c, fetch=fake_returning(page("Selig airfoil measurements", "")))
    assert status == "PASS"
    assert "selig" in msg and "airfoil" in msg


# ---------------------------------------------------------------- redirects (Round 13 K5)

def test_redirect_to_homepage_fails():
    c = cite("https://forum.example.org/t/tailsitter-build/123", "Tailsitter build log")
    fake = fake_returning("<nav>tailsitter</nav>", final_url="https://forum.example.org/")
    status, msg = check(c, fetch=fake)
    assert status == "FAIL"
    assert msg == "redirected to https://forum.example.org/"


def test_redirect_to_other_host_with_no_match_fails():
    c = cite("https://old.example.org/aero", "AeroSandbox (Sharpe 2021)")
    fake = fake_returning(page("Domain for sale", "Buy this domain."),
                          final_url="https://parked.example.net/sale")
    status, msg = check(c, fetch=fake)
    assert status == "FAIL"
    assert msg == "redirected to https://parked.example.net/sale"


def test_redirect_to_other_host_with_matching_title_passes():
    c = cite("https://old.example.org/aero", "AeroSandbox (Sharpe 2021)")
    fake = fake_returning(page("AeroSandbox Toolkit"), final_url="https://www.example.net/aero-sandbox")
    status, _ = check(c, fetch=fake)
    assert status == "PASS"


def test_redirect_to_same_host_page_with_matching_title_passes():
    c = cite("https://example.org/old-path", "Bixler Scratch Build")
    fake = fake_returning(page("Bixler Scratch Build"), final_url="https://example.org/articles/bixler")
    status, _ = check(c, fetch=fake)
    assert status == "PASS"


def test_trailing_slash_only_is_not_a_redirect():
    c = cite("https://example.org/", "Bixler Scratch Build")
    fake = fake_returning(page("Bixler Scratch Build"), final_url="https://example.org")
    status, _ = check(c, fetch=fake)
    assert status == "PASS"


# ---------------------------------------------------------------- extraction

def test_extract_knowledge_frontmatter_and_link():
    text = (
        "---\n"
        "id: demo\n"
        'title: "Bixler Scratch Build"\n'
        "source_url: https://flitetest.com/articles/bixler\n"
        "---\n"
        "\n"
        "See [Wikipedia](https://en.wikipedia.org/wiki/Convair_XFY_Pogo) for more.\n"
    )
    cites = extract_citations(text, "knowledge/diy-projects/demo.md")
    assert [(c.url, c.claimed_text, c.line) for c in cites] == [
        ("https://flitetest.com/articles/bixler", "Bixler Scratch Build", 4),
        ("https://en.wikipedia.org/wiki/Convair_XFY_Pogo", "Wikipedia", 7),
    ]


@pytest.mark.parametrize("text", [
    # quoted value, extra spaces around the colon and value
    "---\ntitle: CRLF Title\nsource_url:   \"https://example.org/k\"   \n---\n",
    # indented key, single quotes
    "---\ntitle: CRLF Title\n  source_url: 'https://example.org/k'\n---\n",
    # Windows line endings
    "---\r\ntitle: CRLF Title\r\nsource_url: https://example.org/k\r\n---\r\n",
    # BOM at the start of the file
    "﻿---\ntitle: CRLF Title\nsource_url: https://example.org/k\n---\n",
])
def test_source_url_variants_are_extracted(text):
    cites = extract_citations(text, "knowledge/sources/x.md")
    assert [(c.url, c.claimed_text) for c in cites] == [("https://example.org/k", "CRLF Title")]


def test_source_url_after_other_frontmatter_keys_is_extracted():
    text = ("---\ntags: [a, b]\nsummary: |\n  text here\nsource_url: https://example.org/k\n"
            "title: Key Title\n---\n")
    cites = extract_citations(text, "knowledge/sources/x.md")
    assert [(c.url, c.claimed_text, c.line) for c in cites] == [
        ("https://example.org/k", "Key Title", 5)]


def test_extract_standards_source_string():
    text = (
        "params:\n"
        "  tensile:\n"
        '    source: "UltiMaker PETG Technical Data Sheet v1.00 (2022-04-29), '
        '(https://um-support-files.ultimaker.com/PETG-TDS-v1.00.pdf, checked 2026-11-16)."\n'
    )
    cites = extract_citations(text, "standards/design-standards.yaml")
    assert len(cites) == 1
    assert cites[0].url == "https://um-support-files.ultimaker.com/PETG-TDS-v1.00.pdf"
    assert cites[0].line == 3
    assert "https://" not in cites[0].claimed_text
    assert cites[0].claimed_text.startswith("UltiMaker PETG Technical Data Sheet")


def test_standards_source_url_key_uses_sibling_name():
    text = (
        "machines:\n"
        "  - id: laser\n"
        '    name: "Universal Systems laser cutter"\n'
        "    source_url: https://example.org/labs/\n"
    )
    cites = extract_citations(text, "standards/manufacturing.yaml")
    assert [(c.url, c.claimed_text, c.line) for c in cites] == [
        ("https://example.org/labs/", "Universal Systems laser cutter", 4)]


# ---------------------------------------------------------------- added lines

def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.org",
                    *args], check=True, capture_output=True)


def test_added_citations_only_new_lines(tmp_path):
    repo = tmp_path
    (repo / "knowledge").mkdir()
    f = repo / "knowledge" / "note.md"
    f.write_text("---\ntitle: Old Note\nsource_url: https://example.org/old\n---\n")
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")

    f.write_text(f.read_text() + "\nNew link [Fresh Page](https://example.org/new)\n")
    cites = added_citations("HEAD", repo_root=repo)
    assert [(c.url, c.claimed_text, c.path, c.line) for c in cites] == [
        ("https://example.org/new", "Fresh Page", "knowledge/note.md", 6),
    ]


def test_url_added_inside_existing_line_and_plus_prefixed_line_are_found(tmp_path):
    repo = tmp_path
    (repo / "knowledge").mkdir()
    f = repo / "knowledge" / "note.md"
    f.write_text("---\ntitle: Old Note\nsource_url: https://example.org/old\n---\n"
                 "See [Old Page](https://example.org/a) here.\n")
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")

    f.write_text("---\ntitle: Old Note\nsource_url: https://example.org/old\n---\n"
                 "See [Old Page](https://example.org/a) and [Added Link](https://example.org/b).\n"
                 "++ [Plus Line](https://example.org/plus)\n")
    cites = added_citations("HEAD", repo_root=repo)
    assert [(c.url, c.line) for c in cites] == [
        ("https://example.org/a", 5),
        ("https://example.org/b", 5),
        ("https://example.org/plus", 6),
    ]
