"""Scraper `tec_ical`: the iCal export of a WordPress site using "The Events Calendar".

Many small organizations run WordPress with The Events Calendar plugin. Its
list view offers an iCalendar export (the calendar address with `?ical=1`),
which gives each event's title, start, end, place, categories and a link to
its own page. This scraper reads that export. It works for any standard
iCalendar feed with the same fields.

What it takes from each event: title (SUMMARY), start and end (DTSTART,
DTEND), address (LOCATION), link (URL), categories (CATEGORIES, used only
for the source's filter rule), and a repeat rule (RRULE) if one is given.

What it never takes: the description, images or attachments (facts and a
link only), and the organizer, attendee or contact fields (nothing about
people). Everything else comes from the source entry or stays unknown; see
`pvscrapers.core`. A source entry may also set `listing_title` and
`signup_url_always` (see `pvscrapers.core`) when each public event on its
calendar is a volunteer shift with its own title and sign-up page.

Events it drops, each reported with a reason: no title; no readable start;
an all-day event (the export gives no start time, and we never guess one);
a time with no time zone when neither the feed nor the source names one;
cancelled; no link; missing a category the source requires; the same event
twice in one feed.
"""

from __future__ import annotations

import re
from datetime import datetime

from pvscrapers import ical
from pvscrapers.core import Dropped, ParseResult, SourceDefaults

NAME = "tec_ical"

_RRULE = re.compile(
    r"^FREQ=(SECONDLY|MINUTELY|HOURLY|DAILY|WEEKLY|MONTHLY|YEARLY)(;[A-Z]+=[^;]+)*$"
)


def parse(page_text: str, source: dict, fetched_at: datetime) -> list[dict]:
    """Listings from one downloaded feed. No network. See parse_with_report."""
    return parse_with_report(page_text, source, fetched_at).events


def parse_with_report(page_text: str, source: dict, fetched_at: datetime) -> ParseResult:
    """Listings from one downloaded feed, plus every dropped event and why.

    Raises core.SourceError for a bad source entry and ical.ICalError when
    the text is not an iCalendar file (both mean: report a broken scraper).
    """
    if fetched_at.tzinfo is None:
        raise ValueError("fetched_at needs a time zone")
    defaults = SourceDefaults.from_source(source)
    calendar = ical.parse(page_text)
    feed_zone = ical.zone(calendar.text("X-WR-TIMEZONE")) or ical.zone(defaults.timezone)

    result = ParseResult()
    seen: set[str] = set()
    for event in calendar.walk("VEVENT"):
        title = _one_line(event.text("SUMMARY"))
        start_prop = event.first("DTSTART")
        start_text = start_prop.value.strip() if start_prop else None
        categories = [
            item for prop in event.all("CATEGORIES") for item in ical.split_list(prop.value)
        ]

        def drop(
            reason: str,
            title: str | None = title,
            start: str | None = start_text,
            categories: list[str] = categories,
        ) -> None:
            result.dropped.append(
                Dropped(
                    title=title or "(no title)",
                    start=start,
                    reason=reason,
                    categories=list(categories),
                )
            )

        if not title:
            drop("no title")
            continue
        if start_prop is None:
            drop("no start date")
            continue
        try:
            start = ical.read_when(start_prop, feed_zone)
        except ical.ICalError as error:
            drop(f"start could not be read ({error})")
            continue
        if start.all_day:
            drop("all-day event: the feed gives no start time", start=start.value.isoformat())
            continue
        if start.floating:
            drop("start time has no time zone, and none is set for the feed or source")
            continue
        start_at = _local(start.value, feed_zone)
        start_text = start_at.isoformat()

        if (event.text("STATUS") or "").upper() == "CANCELLED":
            drop("cancelled", start=start_text)
            continue
        missing = defaults.missing_categories(categories)
        if missing:
            drop(f"not in required categories: {', '.join(missing)}", start=start_text)
            continue
        end_at = _end(event, feed_zone, start_at)

        link = _web_link(event.text("URL")) or defaults.signup_url
        if not link:
            drop("no link to the event's own page", start=start_text)
            continue

        own_id = event.text("UID") or f"{start_at.isoformat()}|{title}"
        recurrence_id = event.first("RECURRENCE-ID")
        if recurrence_id is not None:
            own_id += f"|{recurrence_id.value.strip()}"
        if own_id in seen:
            drop("the same event appears twice in the feed", start=start_text)
            continue
        seen.add(own_id)

        result.events.append(
            defaults.listing(
                own_id=own_id,
                title=title,
                start=start_at,
                end=end_at,
                address=_address(event.text("LOCATION")),
                link=link,
                fetched_at=fetched_at,
                recurrence_rule=_rrule(event),
            )
        )
    return result


def _one_line(text: str | None) -> str | None:
    if text is None:
        return None
    return re.sub(r"\s+", " ", text).strip() or None


def _address(text: str | None) -> str | None:
    if text is None:
        return None
    parts = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"[,\n]", text)]
    return ", ".join(p for p in parts if p) or None


def _web_link(text: str | None) -> str | None:
    if text and re.match(r"^https?://\S+$", text.strip()):
        return text.strip()
    return None


def _local(moment: datetime, feed_zone) -> datetime:
    """Show a UTC time in the feed's own zone when it names one (same moment)."""
    if (
        feed_zone is not None
        and moment.utcoffset() is not None
        and moment.utcoffset().total_seconds() == 0
    ):
        return moment.astimezone(feed_zone)
    return moment


def _end(event: ical.Component, feed_zone, start_at: datetime) -> datetime | None:
    """The end time, or None when the feed gives none we can trust."""
    prop = event.first("DTEND")
    if prop is None:
        return None
    try:
        end = ical.read_when(prop, feed_zone)
    except ical.ICalError:
        return None
    if end.all_day or end.floating:
        return None
    end_at = _local(end.value, feed_zone)
    return end_at if end_at >= start_at else None


def _rrule(event: ical.Component) -> str | None:
    prop = event.first("RRULE")
    if prop is None:
        return None
    rule = prop.value.strip()
    return rule if _RRULE.match(rule) else None
