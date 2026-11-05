"""Scraper `apostrophe_events`: the "upcoming events" list of a site built with
ApostropheCMS (`apostrophe-events` widget), for example a parks program that
lists many partners' volunteer days.

Each card has the title linking to the event page and up to three small
lines: the place (sometimes), the date ("November 7th", no year) and the
times ("9:00am – 10:00am").

The year is not on the page. Because the list shows only upcoming events,
the date is taken in the year that puts it between the day before the page
was read and a year after. If the event's address also carries a year (for
example `...-11-2026` or `...-11-7-26`), the two must agree, or the event is
dropped as "year unclear". Nothing else is guessed.

What it takes: title, link, date, times and place (as `address`). No body
text, images or contact details, nothing about people. The listing's
organization is the source's own `org_name` (the page has no field for a
partner host); a platform source like this one is checked by name in the
pipeline's report rules.

Source entry options (besides those in `pvscrapers.core`):
    timezone      required: the page's times are local

Events it drops, each reported with a reason: several days or "All Day" (a
season banner, not a shift); a title in the source's drop_titles; no readable
date or times; year unclear; no link; the same event twice.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from pvscrapers import html, pagetext
from pvscrapers.core import Dropped, ParseResult, SourceDefaults, SourceError

NAME = "apostrophe_events"
_SLUG_MONTH_YEAR = re.compile(r"(?<!\d)(\d{1,2})-(20\d\d)$")
_SLUG_M_D_YY = re.compile(r"(?<!\d)(\d{1,2})-(\d{1,2})-(\d{2})$")
_SLUG_YEAR = re.compile(r"(?<!\d)(20\d\d)(?!\d)")


def parse(page_text: str, source: dict, fetched_at: datetime) -> list[dict]:
    return parse_with_report(page_text, source, fetched_at).events


def slug_year(url: str, month: int, day: int) -> int | None:
    """A year written in the event's address, if any ("...-11-2026", "...-11-7-26")."""
    slug = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    if m := _SLUG_M_D_YY.search(slug):
        if (int(m.group(1)), int(m.group(2))) == (month, day):
            return 2000 + int(m.group(3))
        return None
    if m := _SLUG_MONTH_YEAR.search(slug):
        return int(m.group(2))
    if m := _SLUG_YEAR.search(slug):
        return int(m.group(1))
    return None


def upcoming_year(month: int, day: int, read_on: datetime) -> int | None:
    """The year that puts month/day between the day before read_on and a year after."""
    first = (read_on - timedelta(days=1)).date()
    for year in (first.year, first.year + 1):
        candidate = pagetext.make_date(year, month, day)
        if candidate is not None and first <= candidate < first + timedelta(days=366):
            return year
    return None


def parse_with_report(page_text: str, source: dict, fetched_at: datetime) -> ParseResult:
    if fetched_at.tzinfo is None:
        raise ValueError("fetched_at needs a time zone")
    defaults = SourceDefaults.from_source(source)
    zone = pagetext.page_zone(defaults)
    read_on = fetched_at.astimezone(zone)
    page = html.parse(page_text)
    cards = page.find_all("div", "apostrophe-event-preview")
    if not cards and not page.find(cls="c-upcoming-events"):
        raise SourceError("no events list on this page; the page layout may have changed")

    result = ParseResult()
    seen: set[str] = set()
    for card in cards:
        link = card.find("a", "apostrophe-event-title")
        title = link.text() if link else ""
        lines = [n.text() for n in card.find_all("h5", "apostrophe-event-date")]
        date_lines = [x for x in lines if pagetext.month_days(x)]
        time_lines = [x for x in lines if pagetext.time_range(x) or x.casefold() == "all day"]
        places = [x for x in lines if x not in date_lines and x not in time_lines]
        day_text = date_lines[0] if date_lines else None

        def drop(reason: str, title: str = title, day_text: str | None = day_text) -> None:
            result.dropped.append(
                Dropped(title=title or "(no title)", start=day_text, reason=reason)
            )

        if not title:
            drop("no title")
            continue
        href = (link.attrs.get("href") or "").strip() if link else ""
        if not href.startswith("http"):
            drop("no link to the event")
            continue
        if href in seen:
            drop("the same event twice on this page")
            continue
        seen.add(href)
        days = pagetext.month_days(day_text or "")
        if len(days) > 1 or any(x.casefold() == "all day" for x in time_lines):
            drop("runs over several days or all day (a season banner, not a shift)")
            continue
        if match := defaults.drop_title_match(title):
            drop(f"title matches the source's drop rule: {match}")
            continue
        if len(days) != 1:
            drop("date could not be read")
            continue
        month, day_of_month = days[0]
        year = upcoming_year(month, day_of_month, read_on)
        written = slug_year(href, month, day_of_month)
        if year is None or (written is not None and written != year):
            drop("year unclear (the page gives none, and the event's address disagrees)")
            continue
        day = pagetext.make_date(year, month, day_of_month)
        times = pagetext.time_range(time_lines[0]) if time_lines else None
        if day is None or times is None:
            drop("date or times could not be read")
            continue
        result.events.append(
            defaults.listing(
                own_id=href,
                title=title,
                start=pagetext.local(day, times[0], zone),
                end=pagetext.local(day, times[1], zone),
                address=places[0] if places else None,
                link=href,
                fetched_at=fetched_at,
            )
        )
    return result
