"""Every scraper in the package, by the name a source entry uses in `scraper:`."""

from __future__ import annotations

from datetime import UTC, datetime
from types import ModuleType

from pvscrapers.core import ParseResult
from pvscrapers.fetch import Fetcher
from pvscrapers.scrapers import (
    accordion_event_list,
    apostrophe_events,
    bl_events,
    mec_events,
    tec_ical,
)

SCRAPERS: dict[str, ModuleType] = {
    tec_ical.NAME: tec_ical,
    accordion_event_list.NAME: accordion_event_list,
    bl_events.NAME: bl_events,
    apostrophe_events.NAME: apostrophe_events,
    mec_events.NAME: mec_events,
}


def get(name: str) -> ModuleType:
    """The scraper module for a source entry's `scraper:` value."""
    try:
        return SCRAPERS[name]
    except KeyError:
        raise KeyError(f"no scraper named {name!r}; known: {', '.join(sorted(SCRAPERS))}") from None


def scrape(source: dict, fetcher: Fetcher, fetched_at: datetime | None = None) -> ParseResult:
    """Fetch one source politely, then parse it. Fetch errors are raised, not hidden."""
    scraper = get(source.get("scraper", ""))
    response = fetcher.fetch_source(source)
    when = fetched_at or datetime.now(UTC)
    return scraper.parse_with_report(response.text(), source, when)
