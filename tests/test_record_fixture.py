"""The fixture-recording tool (tests/record_fixture.py), with a fake site: no network."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
import record_fixture

from pvscrapers.fetch import Fetcher, Response

CONTACT = "bot-contact@example.org"
FEED = "https://org.example.org/events/?ical=1"
ICS = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nX-WR-TIMEZONE:America/New_York\r\nBEGIN:VEVENT\r\n"
    "UID:1@example.org\r\nSUMMARY:Park cleanup\r\n"
    "DTSTART;TZID=America/New_York:20261020T090000\r\n"
    "URL:https://org.example.org/event/cleanup/\r\nCATEGORIES:Volunteer\r\n"
    "DESCRIPTION:Long text by the organization\r\n  that runs over two lines.\r\n"
    "ATTACH;FMTTYPE=image/jpeg:https://org.example.org/photo.jpg\r\n"
    "ORGANIZER;CN=A. Person:mailto:a.person@example.org\r\n"
    "END:VEVENT\r\nEND:VCALENDAR\r\n"
)
SOURCE = {
    "id": "example-org",
    "org_name": "Example Org",
    "scraper": "tec_ical",
    "url": FEED,
    "area": "example-city",
    "listing_language": "en",
    "default_type": "service",
    "sensitive": False,
    "crawl_delay_seconds": 7,
}


class Site:
    def __init__(self):
        self.urls, self.waits, self.now = [], [], 0.0

    def transport(self, url, headers, timeout, max_bytes):
        self.urls.append(url)
        if url.endswith("/robots.txt"):
            return Response(url, 200, {}, b"User-agent: *\nCrawl-delay: 2\nDisallow:")
        return Response(url, 200, {"content-type": "text/calendar"}, ICS.encode())

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


def fetcher(site: Site) -> Fetcher:
    return Fetcher(CONTACT, transport=site.transport, clock=lambda: site.now, sleep=site.sleep)


NOW = datetime.fromisoformat("2026-10-14T10:00:00-04:00")


def test_records_through_fetch_source_with_the_source_delay(tmp_path):
    site = Site()
    record_fixture.record(SOURCE, fetcher(site), tmp_path, now=NOW)
    assert site.urls == ["https://org.example.org/robots.txt", FEED]
    assert site.waits == [7]  # source delay beats robots.txt's 2 s


def test_removes_descriptions_images_and_people(tmp_path):
    summary = record_fixture.record(SOURCE, fetcher(Site()), tmp_path, now=NOW)
    page = (tmp_path / "page.ics").read_text(encoding="utf-8")
    assert "Long text" not in page and "two lines" not in page
    assert "photo.jpg" not in page and "Person" not in page and "mailto" not in page
    assert record_fixture.ICAL_PLACEHOLDER in page
    assert summary["removed"] == {"ATTACH": 1, "DESCRIPTION": 1, "ORGANIZER": 1}
    fetched = json.loads((tmp_path / "fetched.json").read_text())
    assert fetched["fetched_at"] == "2026-10-14T10:00:00-04:00"
    assert CONTACT not in json.dumps(fetched) and FEED not in json.dumps(fetched)


def test_writes_expected_only_with_an_invented_source(tmp_path):
    summary = record_fixture.record(SOURCE, fetcher(Site()), tmp_path, now=NOW)
    assert summary["listings"] is None and not (tmp_path / "expected.json").exists()
    (tmp_path / "source.json").write_text(json.dumps({**SOURCE, "id": "invented"}))
    summary = record_fixture.record(SOURCE, fetcher(Site()), tmp_path, now=NOW, replace=True)
    assert summary["listings"] == 1
    expected = json.loads((tmp_path / "expected.json").read_text())
    assert expected[0]["source_id"] == "invented"


def test_will_not_overwrite_without_replace(tmp_path):
    record_fixture.record(SOURCE, fetcher(Site()), tmp_path, now=NOW)
    site = Site()
    with pytest.raises(record_fixture.Refused):
        record_fixture.record(SOURCE, fetcher(site), tmp_path, now=NOW)
    assert site.urls == []


@pytest.mark.parametrize(
    "change",
    [
        {"sensitive": None},
        {"sensitive": True},
        {"default_type": "campaign"},
        {"default_type": "protest_action"},
        {"scraper": "no-cleaner-yet"},
    ],
)
def test_never_records_sensitive_campaign_or_unknown_sources(tmp_path, change):
    source = {k: v for k, v in {**SOURCE, **change}.items() if v is not None}
    site = Site()
    with pytest.raises(record_fixture.Refused):
        record_fixture.record(source, fetcher(site), tmp_path, now=NOW)
    assert site.urls == []


def test_command_line_needs_a_contact(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("PV_CONTACT_EMAIL", raising=False)
    entry = tmp_path / "entry.json"
    entry.write_text(json.dumps(SOURCE))
    assert record_fixture.main(["--source", str(entry), "--out", str(tmp_path / "f")]) == 1
    assert "PV_CONTACT_EMAIL" in capsys.readouterr().out


def test_command_line_reminds_about_the_notice(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PV_CONTACT_EMAIL", CONTACT)
    site = Site()
    real = record_fixture.Fetcher
    monkeypatch.setattr(
        record_fixture,
        "Fetcher",
        lambda contact: real(
            contact, transport=site.transport, clock=lambda: site.now, sleep=site.sleep
        ),
    )
    entry = tmp_path / "entry.json"
    entry.write_text(json.dumps(SOURCE))
    assert record_fixture.main(["--source", str(entry), "--out", str(tmp_path / "f")]) == 0
    out = capsys.readouterr().out
    assert "tests/fixtures/NOTICE.md" in out
    assert "expected.json and dropped.json" in out and "whole case folder" in out


def test_notice_exists():
    from pathlib import Path

    notice = Path(record_fixture.__file__).parent / "fixtures" / "NOTICE.md"
    text = notice.read_text(encoding="utf-8")
    assert "not** covered by this repository's MIT licence" in text
    assert "not ours to license" in text and "whole case folder is deleted" in text
