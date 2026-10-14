"""Every scraper on its recorded pages, with the network off (PROJECT.md section 4).

Layout (tests/README.md): tests/fixtures/<scraper>/<case>/ holds
    page.*          a recorded copy of a public calendar page, people's names removed
    source.json     an invented source entry
    expected.json   the listings the scraper should produce
    dropped.json    the events it should drop, with the reason (optional)
    fetched.json    when the page was recorded ("fetched_at") and what was removed

Checks: output matches expected.json and the event schema, is not empty, has
unique ids, never holds a field outside the schema (so no attendee or sign-up
data), and the recorded page holds no people fields.
"""

from __future__ import annotations

import json
import re
import socket
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pytest

from guards import event_schema
from pvscrapers import scrapers

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
PEOPLE_FIELDS = re.compile(r"^(ORGANIZER|ATTENDEE|CONTACT)[;:]", re.MULTILINE)


def cases() -> list[Path]:
    return sorted(
        case
        for name in scrapers.SCRAPERS
        if (FIXTURES / name).is_dir()
        for case in (FIXTURES / name).iterdir()
        if (case / "source.json").is_file()
    )


def _page(case: Path) -> Path:
    pages = sorted(case.glob("page.*"))
    assert len(pages) == 1, f"{case}: needs exactly one page.* file"
    return pages[0]


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a parse step tried to use the network")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


def _run(case: Path):
    scraper = scrapers.get(case.parent.name)
    source = _read_json(case / "source.json")
    fetched_at = datetime.fromisoformat(_read_json(case / "fetched.json")["fetched_at"])
    text = _page(case).read_text(encoding="utf-8")
    return scraper, source, fetched_at, text


def test_every_scraper_has_a_fixture():
    have = {case.parent.name for case in cases()}
    missing = sorted(set(scrapers.SCRAPERS) - have)
    assert not missing, f"scrapers without a recorded fixture: {missing}"


@pytest.mark.parametrize("case", cases(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_output_matches_expected(case: Path, no_network):
    scraper, source, fetched_at, text = _run(case)
    result = scraper.parse_with_report(text, source, fetched_at)
    assert result.events, "the scraper found no listings on its recorded page"
    assert result.events == _read_json(case / "expected.json")
    assert scraper.parse(text, source, fetched_at) == result.events
    if (case / "dropped.json").is_file():
        assert [asdict(d) for d in result.dropped] == _read_json(case / "dropped.json")


@pytest.mark.parametrize("case", cases(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_output_matches_schema(case: Path, no_network):
    scraper, source, fetched_at, text = _run(case)
    events = scraper.parse(text, source, fetched_at)
    data = {"generated_at": fetched_at.isoformat(), "events": events}
    errors = event_schema.schema_errors(event_schema.file_validator(ROOT), data)
    assert not errors, "\n".join(errors)
    assert not event_schema.duplicate_ids(data)
    assert all(e["last_seen_at"] == fetched_at.isoformat() for e in events)
    assert all(e["source_id"] == source["id"] for e in events)


@pytest.mark.parametrize("case", cases(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_recorded_page_holds_no_people_fields(case: Path):
    text = _page(case).read_text(encoding="utf-8")
    assert not PEOPLE_FIELDS.search(text), "organizer, attendee or contact lines in a fixture"
    assert "mailto:" not in text.lower()


@pytest.mark.parametrize("case", cases(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_fetch_date_is_recorded(case: Path):
    fetched = _read_json(case / "fetched.json")
    assert datetime.fromisoformat(fetched["fetched_at"]).tzinfo is not None
