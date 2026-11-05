"""Scraper `bl_events`: a WordPress events list made of `<article class="the-event">`
cards (a custom "bl_events" event type, filtered by category in the address).

Each card shows the day without a year ("Saturday, November 7"), the times
("9:00 am - 12:00 pm"), the title linking to the event page, a short teaser,
and the place. The year is read from the link's `eDate=YYYYMMDD`, never
guessed; the link's month and day must match the card's.

What it takes: title, link, date, times and place name (as `address`). The
teaser is read only to drop an event that asks for money (PROJECT.md 8:
pay-to-volunteer is never listed). No images, nothing about people.

Source entry options (besides those in `pvscrapers.core`):
    timezone      required: the page's times are local

Events it drops, each reported with a reason: a multi-day event (a season
banner, not a shift); a title in the source's drop_titles; a price or fee in
the teaser; no `eDate` in the link, or one that disagrees with the card; no
readable times; no link; the same event twice.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

from pvscrapers import html, pagetext
from pvscrapers.core import Dropped, ParseResult, SourceDefaults, SourceError

NAME = "bl_events"
_PRICE = re.compile(r"\$\s*\d|\b(fee|fees|price|tickets?)\b", re.IGNORECASE)


def parse(page_text: str, source: dict, fetched_at: datetime) -> list[dict]:
    return parse_with_report(page_text, source, fetched_at).events


def _text(node: html.Node, cls: str) -> str:
    found = node.find(cls=cls)
    return found.text() if found else ""


def parse_with_report(page_text: str, source: dict, fetched_at: datetime) -> ParseResult:
    if fetched_at.tzinfo is None:
        raise ValueError("fetched_at needs a time zone")
    defaults = SourceDefaults.from_source(source)
    zone = pagetext.page_zone(defaults)
    page = html.parse(page_text)
    cards = page.find_all("article", "the-event")
    if not cards and not page.find(cls="search-filter-results"):
        raise SourceError("no event list on this page; the page layout may have changed")

    result = ParseResult()
    seen: set[tuple[str, str]] = set()
    for card in cards:
        heading = card.find("h2")
        link = heading.find("a") if heading else None
        title = link.text() if link else ""
        day_text = _text(card, "date-desc")
        time_text = _text(card, "time-desc")

        def drop(reason: str, title: str = title, day_text: str = day_text) -> None:
            result.dropped.append(
                Dropped(title=title or "(no title)", start=day_text or None, reason=reason)
            )

        if not title:
            drop("no title")
            continue
        href = (link.attrs.get("href") or "").strip() if link else ""
        if not href.startswith("http"):
            drop("no link to the event")
            continue
        days = pagetext.month_days(day_text)
        if len(days) > 1:
            drop("runs over several days (a season banner, not a shift)")
            continue
        if match := defaults.drop_title_match(title):
            drop(f"title matches the source's drop rule: {match}")
            continue
        if _PRICE.search(_text(card, "desc")):
            drop("asks for a price or fee (pay-to-volunteer is never listed)")
            continue
        stamp = (parse_qs(urlsplit(href).query).get("eDate") or [""])[0]
        if not re.fullmatch(r"\d{8}", stamp):
            drop("no year in the event link (eDate)")
            continue
        day = pagetext.make_date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:]))
        if day is None or days != [(day.month, day.day)]:
            drop("the date on the card and in the link do not agree")
            continue
        times = pagetext.time_range(time_text)
        if times is None:
            drop("times could not be read")
            continue
        own = urlsplit(href)
        key = (own.path, stamp)
        if key in seen:
            drop("the same event twice on this page")
            continue
        seen.add(key)
        place = _text(card, "the-location") or None
        link_back = f"{own.scheme}://{own.netloc}{own.path}?eDate={stamp}"
        result.events.append(
            defaults.listing(
                own_id=f"{own.path}?eDate={stamp}",
                title=title,
                start=pagetext.local(day, times[0], zone),
                end=pagetext.local(day, times[1], zone),
                address=place,
                link=link_back,
                fetched_at=fetched_at,
            )
        )
    return result
