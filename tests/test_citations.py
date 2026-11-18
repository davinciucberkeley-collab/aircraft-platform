"""Citation check. No network: every test injects a fake fetch."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aircraft_platform.citations import (Citation, added_citations, check, extract_citations)

LAW_REVIEW_URL = "https://dspace.mit.edu/handle/1721.1/130873"
LAW_REVIEW_TITLE = ("Changes and Opportunities in the Environment for Technology Bargaining | "
                    "Notre Dame Law Review")


def page(title: str, body: str = "") -> str:
    return f"<html><head><title>{title}</title></head><body>{body}</body></html>"


def fake_returning(html: str):
    calls = []

    def fetch(url):
        calls.append(url)
        return "text/html; charset=utf-8", html
    fetch.calls = calls
    return fetch


def cite(url: str, claimed: str) -> Citation:
    return Citation(url, claimed, "standards/design-standards.yaml", 1)


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
        return "application/pdf", "%PDF-1.4"
    status, _ = check(cite("https://example.org/a.pdf", "Some Report Title"), fetch=fetch)
    assert status == "WARN"


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


def test_extract_standards_source_string():
    text = (
        "材料: x\n"
        "params:\n"
        "  tensile:\n"
        '    source: "UltiMaker PETG Technical Data Sheet v1.00 (2022-04-29), '
        '(https://um-support-files.ultimaker.com/PETG-TDS-v1.00.pdf, checked 2026-11-16)."\n'
    ).replace("材料: x\n", "")
    cites = extract_citations(text, "standards/design-standards.yaml")
    assert len(cites) == 1
    assert cites[0].url == "https://um-support-files.ultimaker.com/PETG-TDS-v1.00.pdf"
    assert cites[0].line == 3
    assert "https://" not in cites[0].claimed_text
    assert cites[0].claimed_text.startswith("UltiMaker PETG Technical Data Sheet")


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
