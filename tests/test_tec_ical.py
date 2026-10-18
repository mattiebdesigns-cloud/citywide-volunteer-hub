"""Scraper tec_ical on small invented feeds: every rule, one at a time (PROJECT.md 4)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pvscrapers import ical, scrapers
from pvscrapers.core import SourceError, event_id
from pvscrapers.scrapers import tec_ical

FETCHED = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)

SOURCE = {
    "id": "example-org",
    "org_name": "Example Org",
    "scraper": "tec_ical",
    "url": "https://org.example.org/events/?ical=1",
    "area": "example-city",
    "listing_language": "en",
    "default_type": "service",
}


def feed(*events: str, header: str = "X-WR-TIMEZONE:America/New_York") -> str:
    body = "\r\n".join(f"BEGIN:VEVENT\r\n{e.strip()}\r\nEND:VEVENT" for e in events)
    return f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n{header}\r\n{body}\r\nEND:VCALENDAR\r\n"


def event(uid="1@example.org", summary="Park cleanup", extra="", start=None) -> str:
    start = start or "DTSTART;TZID=America/New_York:20261020T090000"
    lines = [
        f"UID:{uid}",
        f"SUMMARY:{summary}",
        start,
        "DTEND;TZID=America/New_York:20261020T120000",
        "URL:https://org.example.org/event/cleanup/",
        "LOCATION:Example Park\\, 1 Main St\\, Example City",
        "CATEGORIES:Volunteer,Free",
        "DESCRIPTION:Long text written by the organization that we never copy.",
    ]
    return "\r\n".join(lines + ([extra] if extra else []))


def run(text: str, **changes):
    source = {**SOURCE, **changes}
    return tec_ical.parse_with_report(text, source, FETCHED)


def test_registered_under_its_name():
    assert scrapers.get("tec_ical") is tec_ical
    with pytest.raises(KeyError):
        scrapers.get("no-such-scraper")


def test_facts_and_link_only():
    result = run(feed(event()))
    (listing,) = result.events
    assert listing["title"] == "Park cleanup"
    assert listing["start"] == "2026-10-20T09:00:00-04:00"
    assert listing["end"] == "2026-10-20T12:00:00-04:00"
    assert listing["address"] == "Example Park, 1 Main St, Example City"
    assert (
        listing["signup_url"] == listing["source_url"] == "https://org.example.org/event/cleanup/"
    )
    assert listing["last_seen_at"] == "2026-10-14T12:00:00+00:00"
    assert listing["id"] == event_id("example-org", "1@example.org")
    assert "never copy" not in repr(listing)


def test_unknown_stays_unknown_when_source_says_nothing():
    (listing,) = run(feed(event())).events
    assert listing["cause"] is None
    assert listing["join_method"] == "unknown"
    assert listing["spanish_spoken"] == "unknown"
    assert listing["min_age"] is None
    assert listing["neighborhood_or_town"] is None
    for key in ("training_required", "clearances_required", "group_friendly"):
        assert listing[key] is None
    assert listing["photos_allowed"] is True
    assert listing["sensitive"] is True  # unsure means sensitive
    assert listing["recurring"] is False and listing["recurrence_rule"] is None


def test_source_defaults_fill_what_the_feed_does_not_say():
    (listing,) = run(
        feed(event()),
        default_cause="parks-and-trees",
        default_join_method="signup",
        sensitive=False,
        default_min_age=12,
        spanish_spoken=True,
        group_friendly=True,
        neighborhood_or_town="Example Hills",
    ).events
    assert listing["cause"] == "parks-and-trees"
    assert listing["join_method"] == "signup"
    assert listing["sensitive"] is False
    assert listing["min_age"] == 12
    assert listing["spanish_spoken"] is True
    assert listing["group_friendly"] is True
    assert listing["neighborhood_or_town"] == "Example Hills"


def test_protest_action_is_always_sensitive():
    (listing,) = run(feed(event()), default_type="protest_action", sensitive=False).events
    assert listing["sensitive"] is True


@pytest.mark.parametrize(
    ("required", "kept"),
    [
        (["Volunteer"], True),
        (["volunteer", "FREE"], True),  # case does not matter
        (["Volunteer", "Free"], True),
        (["Volunteer", "Free", "Outdoors"], False),
        (["Paid"], False),
    ],
)
def test_require_categories_keeps_only_events_with_every_category(required, kept):
    result = run(feed(event()), require_categories=required)
    assert bool(result.events) is kept
    if not kept:
        (dropped,) = result.dropped
        assert dropped.title == "Park cleanup"
        assert dropped.start == "2026-10-20T09:00:00-04:00"
        assert "not in required categories" in dropped.reason


def test_priced_event_in_volunteer_category_is_dropped_and_reported():
    paid = event(uid="2@example.org", summary="Paid social").replace(
        "CATEGORIES:Volunteer,Free", "CATEGORIES:21+,Volunteer"
    )
    result = run(feed(event(), paid), require_categories=["Volunteer", "Free"])
    assert [e["title"] for e in result.events] == ["Park cleanup"]
    assert [(d.title, d.reason) for d in result.dropped] == [
        ("Paid social", "not in required categories: Free")
    ]


def test_categories_over_several_lines_and_escaped_commas():
    text = feed(
        event(extra="CATEGORIES:Trees\\, shrubs and more").replace(
            "CATEGORIES:Volunteer,Free", "CATEGORIES:Volunteer"
        )
    )
    assert run(text, require_categories=["Volunteer", "Trees, shrubs and more"]).events


def test_all_day_event_is_dropped_not_given_a_made_up_time():
    text = feed(
        event(start="DTSTART;VALUE=DATE:20261020").replace(
            "DTEND;TZID=America/New_York:20261020T120000", "DTEND;VALUE=DATE:20261021"
        )
    )
    result = run(text)
    assert not result.events
    assert "all-day" in result.dropped[0].reason


def test_time_without_zone_uses_feed_zone_then_source_zone_else_drops():
    floating = event(start="DTSTART:20261020T090000")
    assert run(feed(floating)).events[0]["start"] == "2026-10-20T09:00:00-04:00"
    no_feed_zone = feed(floating, header="X-WR-CALNAME:Example")
    result = run(no_feed_zone)
    assert not result.events and "no time zone" in result.dropped[0].reason
    with_source_zone = run(no_feed_zone, timezone="America/Chicago")
    assert with_source_zone.events[0]["start"] == "2026-10-20T09:00:00-05:00"


def test_utc_time_shown_in_feed_zone_same_moment():
    (listing,) = run(feed(event(start="DTSTART:20261020T130000Z"))).events
    assert listing["start"] == "2026-10-20T09:00:00-04:00"


def test_unknown_time_zone_name_is_dropped():
    result = run(feed(event(start="DTSTART;TZID=Not/AZone:20261020T090000")))
    assert not result.events and "unknown time zone" in result.dropped[0].reason


def test_end_before_start_becomes_unknown():
    text = feed(event().replace("20261020T120000", "20261020T080000"))
    assert run(text).events[0]["end"] is None


def test_cancelled_event_is_dropped():
    result = run(feed(event(extra="STATUS:CANCELLED")))
    assert not result.events and result.dropped[0].reason == "cancelled"


def test_missing_link_uses_source_signup_url_or_drops():
    no_url = event().replace("URL:https://org.example.org/event/cleanup/\r\n", "")
    assert not run(feed(no_url)).events
    (listing,) = run(feed(no_url), signup_url="https://org.example.org/volunteer/").events
    assert listing["signup_url"] == "https://org.example.org/volunteer/"


def test_same_event_twice_is_kept_once():
    result = run(feed(event(), event()))
    assert len(result.events) == 1
    assert "twice" in result.dropped[0].reason


def test_recurrence_id_makes_occurrences_distinct():
    first = event(extra="RECURRENCE-ID;TZID=America/New_York:20261020T090000")
    second = event(extra="RECURRENCE-ID;TZID=America/New_York:20261027T090000")
    events = run(feed(first, second)).events
    assert len({e["id"] for e in events}) == 2


def test_repeat_rule_passed_through():
    (listing,) = run(feed(event(extra="RRULE:FREQ=WEEKLY;BYDAY=TU"))).events
    assert listing["recurring"] is True
    assert listing["recurrence_rule"] == "FREQ=WEEKLY;BYDAY=TU"
    (odd,) = run(feed(event(extra="RRULE:not a rule"))).events
    assert odd["recurring"] is False and odd["recurrence_rule"] is None


def test_people_fields_are_never_read():
    extra = "ORGANIZER;CN=A. Person:mailto:a.person@example.org\r\nATTENDEE;CN=B. Person:mailto:b@example.org"
    (listing,) = run(feed(event(extra=extra))).events
    assert "Person" not in repr(listing) and "mailto" not in repr(listing)


def test_folded_lines_are_joined():
    text = feed(event(summary="Park clean\r\n up day"))
    assert run(text).events[0]["title"] == "Park cleanup day"


@pytest.mark.parametrize(
    "change",
    [
        {"listing_language": None},
        {"default_type": None},
        {"default_type": "party"},
        {"area": "Example City"},
        {"default_cause": "Food Access"},
        {"default_join_method": "maybe"},
        {"sensitive": "no"},
        {"require_categories": "Volunteer"},
        {"default_min_age": -1},
    ],
)
def test_bad_source_entry_is_refused(change):
    with pytest.raises(SourceError):
        run(feed(event()), **change)


def test_fetch_time_needs_a_zone():
    with pytest.raises(ValueError):
        tec_ical.parse(feed(event()), SOURCE, datetime(2026, 10, 14, 12, 0))


@pytest.mark.parametrize(
    "text", ["<html>not a calendar</html>", "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"]
)
def test_not_a_calendar_is_an_error(text):
    with pytest.raises(ical.ICalError):
        tec_ical.parse(text, SOURCE, FETCHED)


# Listing overrides (source keys listing_title, signup_url_always), for a calendar of public
# events that each need volunteers (PROJECT.md 4; docs/sources page of the source).

VOLUNTEER_PAGE = "https://org.example.org/volunteer/"


def test_listing_title_replaces_every_title():
    two = feed(event(), event(uid="2@example.org", summary="Repair Fair 2026DEC"))
    result = run(two, listing_title="  Volunteer fixer or helper  at a Repair Fair ")
    assert [e["title"] for e in result.events] == ["Volunteer fixer or helper at a Repair Fair"] * 2


def test_signup_url_always_links_the_volunteer_page_and_keeps_the_link_back():
    (listing,) = run(feed(event()), signup_url=VOLUNTEER_PAGE, signup_url_always=True).events
    assert listing["signup_url"] == VOLUNTEER_PAGE
    assert listing["source_url"] == "https://org.example.org/event/cleanup/"


def test_without_overrides_nothing_changes():
    (listing,) = run(feed(event()), signup_url=VOLUNTEER_PAGE).events
    assert listing["title"] == "Park cleanup"
    assert listing["signup_url"] == "https://org.example.org/event/cleanup/"


def test_overrides_do_not_change_ids_or_drop_reports():
    plain = run(feed(event(), event(uid="", summary="")))
    changed = run(
        feed(event(), event(uid="", summary="")),
        listing_title="Volunteer at the fair",
        signup_url=VOLUNTEER_PAGE,
        signup_url_always=True,
    )
    assert [e["id"] for e in changed.events] == [e["id"] for e in plain.events]
    assert changed.dropped == plain.dropped  # an event with no title is still dropped


@pytest.mark.parametrize(
    "changes",
    [
        {"signup_url_always": True},
        {"signup_url_always": "yes", "signup_url": VOLUNTEER_PAGE},
        {"listing_title": ""},
        {"listing_title": 5},
    ],
)
def test_bad_override_keys_are_refused(changes):
    with pytest.raises(SourceError):
        run(feed(event()), **changes)
