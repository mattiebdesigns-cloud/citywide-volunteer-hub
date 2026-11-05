"""Scraper `mec_events`: the visible events list of a WordPress site using the
Modern Events Calendar plugin (MEC; its booking links end in
`?method=mec-booking-modal`).

The list groups events under month headings ("November 2026"); each
`<article class="mec-event-article">` sits in its month's group
(class `mec-toggle-YYYYMM-...`), which gives the year. Each card shows the
title, a date label ("Tue, Nov 10"), start and end times, and the place with
its street address.

Only the visible list is read. The page also carries schema.org data for each
event; it is never read (on the site this was built for, its times were
wrong). The organizer block (a person's name) is never read. The short
description is read only to drop an event that shows a price. A "Sold Out"
label marks the listing full; other labels ("Last Few Tickets") are ignored.

What it takes: title, link to the event's own page, date, times, place and
address. Nothing about people, no images.

Source entry options (besides those in `pvscrapers.core`):
    timezone      required: the page's times are local

Events it drops, each reported with a reason: the source's title rules
(drop_titles, require_titles); a price shown; no month group or a date that
disagrees with it; no readable times; no link; the same event twice.
"""

from __future__ import annotations

import re
from datetime import datetime

from pvscrapers import html, pagetext
from pvscrapers.core import Dropped, ParseResult, SourceDefaults, SourceError

NAME = "mec_events"
_MONTH_GROUP = re.compile(r"^mec-toggle-(20\d\d)(\d\d)-")
_PRICE = re.compile(r"\$\s*\d|\b(fee|fees|price|cost)\b", re.IGNORECASE)
_PRICE_CLASSES = ("mec-event-cost", "mec-price-details", "mec-event-price")


def parse(page_text: str, source: dict, fetched_at: datetime) -> list[dict]:
    return parse_with_report(page_text, source, fetched_at).events


def _text(node: html.Node, cls: str) -> str:
    found = node.find(cls=cls)
    return found.text() if found else ""


def _month_group(card: html.Node) -> tuple[int, int] | None:
    for name in card.classes:
        if m := _MONTH_GROUP.match(name):
            return int(m.group(1)), int(m.group(2))
    return None


def _shows_price(card: html.Node) -> bool:
    for cls in _PRICE_CLASSES:
        found = card.find(cls=cls)
        if found and found.text() and found.text().casefold() not in ("free", "0", "$0"):
            return True
    return bool(_PRICE.search(_text(card, "mec-event-description")))


def parse_with_report(page_text: str, source: dict, fetched_at: datetime) -> ParseResult:
    if fetched_at.tzinfo is None:
        raise ValueError("fetched_at needs a time zone")
    defaults = SourceDefaults.from_source(source)
    zone = pagetext.page_zone(defaults)
    page = html.parse(page_text)
    cards = page.find_all("article", "mec-event-article")
    if not cards and not page.find(cls="mec-wrap"):
        raise SourceError("no events list on this page; the page layout may have changed")

    result = ParseResult()
    seen: set[str] = set()
    for card in cards:
        heading = card.find(cls="mec-event-title")
        link = heading.find("a") if heading else None
        title = link.text() if link else ""
        day_text = _text(card, "mec-start-date-label")

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
        if why := defaults.title_filter(title):
            drop(why)
            continue
        if _shows_price(card):
            drop("shows a price (pay-to-volunteer is never listed)")
            continue
        group = _month_group(card)
        days = pagetext.month_days(day_text)
        if group is None or len(days) != 1 or days[0][0] != group[1]:
            drop("the year could not be read from the month heading")
            continue
        day = pagetext.make_date(group[0], *days[0])
        times = pagetext.time_range(
            f"{_text(card, 'mec-start-time')} - {_text(card, 'mec-end-time')}"
        )
        if day is None or times is None:
            drop("date or times could not be read")
            continue
        if href in seen:
            drop("the same event twice on this page")
            continue
        seen.add(href)
        venue = card.find(cls="mec-venue-details")
        address_node = card.find("address")
        address = address_node.text() if address_node else ""
        place = ""
        if venue is not None:
            for child in venue.children:
                if isinstance(child, html.Node) and child.tag == "span":
                    place = child.text()
                    break
        where = ", ".join(x for x in (place, address) if x) or None
        label = heading.find(cls="mec-event-title-soldout") if heading else None
        full = bool(label and label.text().casefold() == "sold out")
        result.events.append(
            defaults.listing(
                own_id=href,
                title=title,
                start=pagetext.local(day, times[0], zone),
                end=pagetext.local(day, times[1], zone),
                address=where,
                link=href,
                fetched_at=fetched_at,
                full=full,
            )
        )
    return result
