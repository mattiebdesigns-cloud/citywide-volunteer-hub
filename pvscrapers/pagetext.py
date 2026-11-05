"""Reading dates and times as web pages write them ("Saturday, November 7",
"9:00 am - 12:00 pm"). Standard library only; nothing is guessed: a value
that cannot be read gives None, and the scraper drops the event with a reason.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pvscrapers.core import SourceDefaults, SourceError

MONTHS = {
    name: number
    for number, names in enumerate(
        [
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sep", "sept"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ],
        start=1,
    )
    for name in names
}
_MONTH = "|".join(sorted(MONTHS, key=len, reverse=True))
_DAY_OF_MONTH = re.compile(rf"\b({_MONTH})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", re.IGNORECASE)
_YEAR = re.compile(r"\b(20\d\d)\b")
_CLOCK = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s?m\.?", re.IGNORECASE)
_START = r"(\d{1,2})(?::(\d{2}))?\s*(?:([ap])\.?\s?m\.?)?"
_RANGE = re.compile(rf"(?<![\d:]){_START}\s*(?:-|–|—|to)\s*{_CLOCK.pattern}", re.IGNORECASE)


def page_zone(defaults: SourceDefaults) -> ZoneInfo:
    """The source's time zone. Pages give local times with no zone, so a source
    read by a page scraper must name one (`timezone:` in its entry)."""
    if not defaults.timezone:
        raise SourceError(
            f"source entry {defaults.source_id!r}: timezone is required for a page "
            "that shows local times"
        )
    try:
        return ZoneInfo(defaults.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise SourceError(
            f"source entry {defaults.source_id!r}: unknown timezone {defaults.timezone!r}"
        ) from None


def month_days(text: str) -> list[tuple[int, int]]:
    """Every (month, day) written in the text, in order ("November 7th" -> (11, 7))."""
    return [(MONTHS[m.group(1).lower()], int(m.group(2))) for m in _DAY_OF_MONTH.finditer(text)]


def years(text: str) -> list[int]:
    return [int(y) for y in _YEAR.findall(text)]


def _clock(hour: str, minute: str | None, half: str) -> time | None:
    h, m = int(hour), int(minute or 0)
    if not (1 <= h <= 12 and 0 <= m <= 59):
        return None
    if half.lower() == "a":
        h = 0 if h == 12 else h
    else:
        h = 12 if h == 12 else h + 12
    return time(h, m)


def time_range(text: str) -> tuple[time, time] | None:
    """A start and end time like "9:00 am - 12:00 pm", "9:00am – 10:00am" or
    "5:30 - 7:00 pm" (the start takes the end's am or pm, unless that would put
    it after the end)."""
    found = _RANGE.search(text)
    if not found:
        return None
    h1, m1, half1, h2, m2, half2 = found.groups()
    end = _clock(h2, m2, half2)
    if end is None:
        return None
    if half1:
        start = _clock(h1, m1, half1)
    else:
        start = _clock(h1, m1, half2)
        if start is not None and start > end:
            start = _clock(h1, m1, "a" if half2.lower() == "p" else "p")
    return (start, end) if start else None


def local(day: date, clock: time, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, clock, zone)


def make_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
