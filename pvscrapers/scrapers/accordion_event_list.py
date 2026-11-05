"""Scraper `accordion_event_list`: a volunteer page whose dated shifts sit in
collapsible sections, one heading per kind of shift.

The page has sections like

    <div class="accordion">
      <h2>Thursday Stewardship (Weekly)</h2>
      <div class="content"> ... <ul>
        <li><a href="<event page>">Title</a>
            <span>Thursday, November 12, 2026 from 9:00 AM to 12:00 PM</span></li>
      </ul></div>
    </div>

What it takes from each item: the title and link, and the date, year and
times written on the same line. Nothing else: no descriptions, no contact
details, nothing about people. Everything else comes from the source entry or
stays unknown (see `pvscrapers.core`); there is no address, since the meeting
place is sent to those who sign up.

Source entry options (besides those in `pvscrapers.core`):
    timezone          required: the page's times are local
    require_headings  list of heading beginnings, e.g. "Thursday Stewardship".
                      Only items under a heading that starts with one of them
                      are kept; items under any other heading are dropped and
                      reported. Without it every section is read.

Events it drops, each reported with a reason: under a heading the source
does not take; a title in the source's drop_titles; no readable date, year or
times; no link; the same event twice.
"""

from __future__ import annotations

from datetime import datetime

from pvscrapers import html, pagetext
from pvscrapers.core import Dropped, ParseResult, SourceDefaults, SourceError

NAME = "accordion_event_list"


def parse(page_text: str, source: dict, fetched_at: datetime) -> list[dict]:
    return parse_with_report(page_text, source, fetched_at).events


def _headings(source: dict) -> tuple[str, ...]:
    wanted = source.get("require_headings") or []
    if not isinstance(wanted, list) or not all(isinstance(h, str) and h.strip() for h in wanted):
        raise SourceError(
            f"source entry {source.get('id', '?')!r}: require_headings must be a list of text"
        )
    return tuple(" ".join(h.split()).casefold() for h in wanted)


def parse_with_report(page_text: str, source: dict, fetched_at: datetime) -> ParseResult:
    if fetched_at.tzinfo is None:
        raise ValueError("fetched_at needs a time zone")
    defaults = SourceDefaults.from_source(source)
    zone = pagetext.page_zone(defaults)
    wanted = _headings(source)
    page = html.parse(page_text)
    sections = page.find_all("div", "accordion")
    if not sections:
        raise SourceError("no shift sections on this page; the page layout may have changed")

    result = ParseResult()
    seen: set[str] = set()
    for section in sections:
        heading_node = section.find("h2") or section.find("h3")
        heading = heading_node.text() if heading_node else ""
        take = not wanted or heading.casefold().startswith(wanted)
        for item in section.find_all("li"):
            link = item.find("a")
            title = link.text() if link else ""
            when = item.text().replace(title, "", 1) if title else item.text()

            def drop(reason: str, title: str = title, when: str = when) -> None:
                result.dropped.append(
                    Dropped(title=title or "(no title)", start=when or None, reason=reason)
                )

            if not take:
                drop(f"not under a heading this source takes ({heading or 'no heading'})")
                continue
            if not title:
                drop("no title")
                continue
            if match := defaults.drop_title_match(title):
                drop(f"title matches the source's drop rule: {match}")
                continue
            href = (link.attrs.get("href") or "").strip() if link else ""
            if not href.startswith("http"):
                drop("no link to the event")
                continue
            days, found_years = pagetext.month_days(when), pagetext.years(when)
            times = pagetext.time_range(when)
            if len(days) != 1 or len(found_years) != 1:
                drop("date or year could not be read")
                continue
            day = pagetext.make_date(found_years[0], *days[0])
            if day is None or times is None:
                drop("date or times could not be read")
                continue
            if href in seen:
                drop("the same event twice on this page")
                continue
            seen.add(href)
            result.events.append(
                defaults.listing(
                    own_id=href,
                    title=title,
                    start=pagetext.local(day, times[0], zone),
                    end=pagetext.local(day, times[1], zone),
                    address=None,
                    link=href,
                    fetched_at=fetched_at,
                )
            )
    return result
