"""The common shape every scraper follows.

A scraper is a module with:

    NAME = "<scraper name>"            # the value of `scraper:` in a source entry
    def parse_with_report(page_text, source, fetched_at) -> ParseResult
    def parse(page_text, source, fetched_at) -> list[dict]   # parse_with_report(...).events

Both parse functions are pure: no network, no files, no clock. `fetched_at`
is passed in, so the same page always gives the same listings.

The source entry
----------------
A source entry is one dict from the city's own (private) source list. A
scraper reads only these keys. Facts the page itself does not give come from
here; anything neither says stays unknown. Nothing is guessed.

Required:
    id                  text; becomes `source_id`
    org_name            text, as the organization writes it
    url                 the page or feed to fetch
    area                area id from the city's settings
    listing_language    language tag the organization writes in, e.g. "en"
    default_type        service | training | campaign | protest_action

Optional (used when the page does not say):
    default_cause         cause id, else null
    default_join_method   drop_in | signup | application, else "unknown"
    sensitive             true or false. Missing means true (the format's rule:
                          when unsure, sensitive). protest_action is always true.
    photos_allowed        default true
    default_min_age       whole number, else null
    spanish_spoken        true or false, else "unknown"
    training_required, clearances_required, group_friendly: true or false, else null
    neighborhood_or_town  text, else null
    signup_url            used only when an event has no link of its own
    timezone              IANA zone, used only for a feed time with no zone

Filter rules (optional, generic, checked before a listing is kept):
    require_categories    list of category names. An event is kept only if
                          its categories include every one (case-insensitive).
                          Every other event is dropped and reported.

Fetching (read by the fetcher, not by parse):
    crawl_delay_seconds   minimum seconds between requests to this site, on
                          top of (never instead of) its robots.txt Crawl-delay
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

TYPES = ("service", "training", "campaign", "protest_action")
JOIN_METHODS = ("drop_in", "signup", "application")
_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_LANGUAGE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


class SourceError(ValueError):
    """The source entry is missing something the scraper needs, or has a bad value."""


@dataclass(frozen=True)
class Dropped:
    """An event on the source page that was not turned into a listing, and why.

    Holds only what the morning report needs: the title, the start as the
    page gave it, and the reason. Never anything about people.
    """

    title: str
    start: str | None
    reason: str


@dataclass
class ParseResult:
    events: list[dict] = field(default_factory=list)
    dropped: list[Dropped] = field(default_factory=list)


def event_id(source_id: str, own_id: str) -> str:
    """Stable listing id: a hash of the source id and the source's own event id."""
    digest = hashlib.sha256(f"{source_id}\x1f{own_id}".encode()).hexdigest()
    return f"{source_id}-{digest[:16]}"


def iso(moment: datetime) -> str:
    """Date-time text with a UTC offset, as the format requires."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("date-time has no time zone")
    return moment.isoformat()


def _required_text(source: dict, key: str) -> str:
    value = source.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SourceError(f"source entry {source.get('id', '?')!r}: {key} is missing")
    return value.strip()


def _optional_bool(source: dict, key: str) -> bool | None:
    value = source.get(key)
    if value is None or isinstance(value, bool):
        return value
    raise SourceError(f"source entry {source.get('id', '?')!r}: {key} must be true or false")


@dataclass(frozen=True)
class SourceDefaults:
    """The facts a source entry supplies, checked once per parse."""

    source_id: str
    org_name: str
    area: str
    listing_language: str
    type: str
    cause: str | None
    join_method: str
    sensitive: bool
    photos_allowed: bool
    min_age: int | None
    spanish_spoken: bool | str
    training_required: bool | None
    clearances_required: bool | None
    group_friendly: bool | None
    neighborhood_or_town: str | None
    signup_url: str | None
    timezone: str | None
    require_categories: tuple[str, ...]

    @classmethod
    def from_source(cls, source: dict[str, Any]) -> SourceDefaults:
        if not isinstance(source, dict):
            raise SourceError("source entry must be a mapping")
        sid = _required_text(source, "id")
        bad = f"source entry {sid!r}"

        area = _required_text(source, "area")
        if not _SLUG.match(area):
            raise SourceError(f"{bad}: area must be an id from the city's settings")
        language = _required_text(source, "listing_language")
        if not _LANGUAGE.match(language):
            raise SourceError(f"{bad}: listing_language must be a language tag like en or es")
        kind = _required_text(source, "default_type")
        if kind not in TYPES:
            raise SourceError(f"{bad}: default_type must be one of {', '.join(TYPES)}")

        cause = source.get("default_cause")
        if cause is not None and not (isinstance(cause, str) and _SLUG.match(cause)):
            raise SourceError(f"{bad}: default_cause must be a cause id")

        join = source.get("default_join_method") or "unknown"
        if join not in (*JOIN_METHODS, "unknown"):
            raise SourceError(
                f"{bad}: default_join_method must be one of {', '.join(JOIN_METHODS)}"
            )

        sensitive = _optional_bool(source, "sensitive")
        sensitive = True if sensitive is None or kind == "protest_action" else sensitive
        photos = _optional_bool(source, "photos_allowed")

        min_age = source.get("default_min_age")
        if min_age is not None and (
            isinstance(min_age, bool) or not isinstance(min_age, int) or min_age < 0
        ):
            raise SourceError(f"{bad}: default_min_age must be a whole number")

        spanish = _optional_bool(source, "spanish_spoken")
        town = source.get("neighborhood_or_town")
        if town is not None and (not isinstance(town, str) or not town.strip()):
            raise SourceError(f"{bad}: neighborhood_or_town must be text")
        signup = source.get("signup_url")
        if signup is not None and not (isinstance(signup, str) and signup.startswith("http")):
            raise SourceError(f"{bad}: signup_url must be a web address")
        tz = source.get("timezone")
        if tz is not None and not isinstance(tz, str):
            raise SourceError(f"{bad}: timezone must be an IANA zone name")

        required = source.get("require_categories") or []
        if not isinstance(required, list) or not all(
            isinstance(c, str) and c.strip() for c in required
        ):
            raise SourceError(f"{bad}: require_categories must be a list of category names")

        return cls(
            source_id=sid,
            org_name=_required_text(source, "org_name"),
            area=area,
            listing_language=language,
            type=kind,
            cause=cause,
            join_method=join,
            sensitive=sensitive,
            photos_allowed=True if photos is None else photos,
            min_age=min_age,
            spanish_spoken="unknown" if spanish is None else spanish,
            training_required=_optional_bool(source, "training_required"),
            clearances_required=_optional_bool(source, "clearances_required"),
            group_friendly=_optional_bool(source, "group_friendly"),
            neighborhood_or_town=town.strip() if town else None,
            signup_url=signup,
            timezone=tz,
            require_categories=tuple(c.strip() for c in required),
        )

    def missing_categories(self, categories: list[str]) -> list[str]:
        """Required categories this event lacks (empty list: keep it)."""
        have = {c.strip().casefold() for c in categories}
        return [c for c in self.require_categories if c.casefold() not in have]

    def listing(
        self,
        *,
        own_id: str,
        title: str,
        start: datetime,
        end: datetime | None,
        address: str | None,
        link: str,
        fetched_at: datetime,
        recurrence_rule: str | None = None,
    ) -> dict:
        """One listing in the shared format: page facts plus this source's defaults."""
        return {
            "id": event_id(self.source_id, own_id),
            "org_name": self.org_name,
            "title": title,
            "start": iso(start),
            "end": iso(end) if end is not None else None,
            "address": address,
            "area": self.area,
            "neighborhood_or_town": self.neighborhood_or_town,
            "cause": self.cause,
            "type": self.type,
            "sensitive": self.sensitive,
            "photos_allowed": self.photos_allowed,
            "signup_url": link,
            "join_method": self.join_method,
            "min_age": self.min_age,
            "listing_language": self.listing_language,
            "spanish_spoken": self.spanish_spoken,
            "training_required": self.training_required,
            "clearances_required": self.clearances_required,
            "group_friendly": self.group_friendly,
            "recurring": recurrence_rule is not None,
            "recurrence_rule": recurrence_rule,
            "source_url": link,
            "source_id": self.source_id,
            "last_seen_at": iso(fetched_at),
        }
