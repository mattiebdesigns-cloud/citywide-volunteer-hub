"""Every scraper in the package, by the name a source entry uses in `scraper:`."""

from __future__ import annotations

from datetime import UTC, datetime
from types import ModuleType

from pvscrapers.core import ParseResult
from pvscrapers.fetch import Fetcher
from pvscrapers.scrapers import tec_ical

SCRAPERS: dict[str, ModuleType] = {
    tec_ical.NAME: tec_ical,
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
