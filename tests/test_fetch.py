"""The polite fetcher and the robots.txt reader (PROJECT.md section 4, rule 1).

No network: a fake transport answers every request and records it, and a
fake clock records every wait.
"""

from __future__ import annotations

import pytest

from pvscrapers import __version__
from pvscrapers.fetch import (
    BOT_NAME,
    Blocked,
    DisallowedByRobots,
    Fetcher,
    FetchError,
    Response,
    user_agent,
)
from pvscrapers.robots import RobotsRules

CONTACT = "bot-contact@example.org"
FEED = "https://org.example.org/events/list/?ical=1"
CALENDAR = b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"


class FakeSite:
    """Answers requests from a table: url -> (status, headers, body)."""

    def __init__(self, pages: dict[str, tuple[int, dict, bytes]]):
        self.pages = pages
        self.requests: list[tuple[str, dict]] = []

    def __call__(self, url, headers, timeout, max_bytes):
        self.requests.append((url, dict(headers)))
        status, found, body = self.pages.get(url, (404, {}, b"not found"))
        return Response(url=url, status=status, headers=found, body=body)

    @property
    def urls(self) -> list[str]:
        return [u for u, _ in self.requests]


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.waits: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.waits.append(round(seconds, 3))
        self.now += seconds


def make(pages, **options):
    site, clock = FakeSite(pages), FakeClock()
    fetcher = Fetcher(CONTACT, transport=site, clock=clock, sleep=clock.sleep, **options)
    return fetcher, site, clock


def robots(text: str) -> tuple[int, dict, bytes]:
    return 200, {"content-type": "text/plain"}, text.encode()


OK = (200, {"content-type": "text/calendar; charset=utf-8"}, CALENDAR)


# -- User-Agent ---------------------------------------------------------------


def test_user_agent_names_the_bot_and_contact():
    assert user_agent(CONTACT) == f"CitywideVolunteerHubBot/{__version__} (+mailto:{CONTACT})"


@pytest.mark.parametrize("contact", ["", "   ", "not-an-address", "a@b"])
def test_no_contact_no_fetcher(contact):
    with pytest.raises(ValueError):
        Fetcher(contact)


def test_contact_comes_from_city_settings():
    fetcher = Fetcher.from_settings({"site": {"contact_email": CONTACT}})
    assert fetcher.user_agent.endswith(f"(+mailto:{CONTACT})")
    with pytest.raises(ValueError):
        Fetcher.from_settings({"site": {}})


def test_every_request_sends_the_bot_user_agent_and_nothing_browser_like():
    fetcher, site, _ = make({"https://org.example.org/robots.txt": robots(""), FEED: OK})
    fetcher.fetch(FEED)
    for _, headers in site.requests:
        assert headers["User-Agent"] == user_agent(CONTACT)
        assert "Mozilla" not in headers["User-Agent"]


@pytest.mark.parametrize(
    "blocked_name",
    [
        "Amazonbot",
        "Applebot-Extended",
        "Bytespider",
        "CCBot",
        "ClaudeBot",
        "Google-Extended",
        "GPTBot",
        "meta-externalagent",
    ],
)
def test_bot_never_uses_a_name_sites_block(blocked_name):
    assert blocked_name.lower() not in user_agent(CONTACT).lower()


# -- robots.txt first ---------------------------------------------------------


def test_robots_txt_is_read_before_anything_else_and_only_once():
    fetcher, site, _ = make({"https://org.example.org/robots.txt": robots(""), FEED: OK})
    fetcher.fetch(FEED)
    fetcher.fetch(FEED)
    assert site.urls == ["https://org.example.org/robots.txt", FEED, FEED]


def test_disallowed_address_is_never_fetched():
    fetcher, site, _ = make(
        {
            "https://org.example.org/robots.txt": robots("User-agent: *\nDisallow: /events/"),
            FEED: OK,
        }
    )
    with pytest.raises(DisallowedByRobots):
        fetcher.fetch(FEED)
    assert site.urls == ["https://org.example.org/robots.txt"]


def test_wildcard_rules_are_obeyed():
    fetcher, site, _ = make(
        {
            "https://org.example.org/robots.txt": robots("User-agent: *\nDisallow: *ical=*"),
            FEED: OK,
        }
    )
    with pytest.raises(DisallowedByRobots):
        fetcher.fetch(FEED)
    assert FEED not in site.urls


def test_missing_robots_txt_allows_fetching():
    fetcher, _, _ = make({FEED: OK})
    assert fetcher.fetch(FEED).status == 200


def test_robots_txt_turned_away_stops_the_source():
    fetcher, site, _ = make({"https://org.example.org/robots.txt": (403, {}, b"no"), FEED: OK})
    with pytest.raises(Blocked):
        fetcher.fetch(FEED)
    assert site.urls == ["https://org.example.org/robots.txt"]


def test_robots_txt_server_error_stops_the_source():
    fetcher, site, _ = make({"https://org.example.org/robots.txt": (500, {}, b""), FEED: OK})
    with pytest.raises(FetchError):
        fetcher.fetch(FEED)
    assert FEED not in site.urls


def test_redirect_to_another_site_reads_that_sites_robots_first():
    other = "https://cdn.example.net/feed.ics"
    fetcher, site, _ = make(
        {
            "https://org.example.org/robots.txt": robots(""),
            FEED: (302, {"location": other}, b""),
            "https://cdn.example.net/robots.txt": robots("User-agent: *\nDisallow: /"),
            other: OK,
        }
    )
    with pytest.raises(DisallowedByRobots):
        fetcher.fetch(FEED)
    assert other not in site.urls
    assert "https://cdn.example.net/robots.txt" in site.urls


# -- delays -------------------------------------------------------------------


def test_robots_crawl_delay_is_honoured():
    fetcher, _, clock = make(
        {
            "https://org.example.org/robots.txt": robots(
                "User-agent: *\nCrawl-delay: 10\nDisallow:"
            ),
            FEED: OK,
        }
    )
    fetcher.fetch(FEED)
    fetcher.fetch(FEED)
    assert clock.waits == [10.0, 10.0]


def test_crawl_delay_on_a_line_before_any_user_agent_counts():
    text = "Crawl-delay: 10\n# START YOAST BLOCK\nUser-agent: *\nDisallow:\n"
    fetcher, _, clock = make({"https://org.example.org/robots.txt": robots(text), FEED: OK})
    fetcher.fetch(FEED)
    assert clock.waits == [10.0]


def test_source_delay_used_when_longer_than_robots():
    fetcher, _, clock = make(
        {
            "https://org.example.org/robots.txt": robots("User-agent: *\nCrawl-delay: 5"),
            FEED: OK,
        }
    )
    fetcher.fetch_source({"id": "x", "url": FEED, "crawl_delay_seconds": 12})
    assert clock.waits == [12.0]


def test_minimum_gap_when_site_sets_none():
    fetcher, _, clock = make({"https://org.example.org/robots.txt": robots(""), FEED: OK})
    fetcher.fetch(FEED)
    assert clock.waits == [1.0]


def test_minimum_gap_never_below_one_second():
    pages = {"https://org.example.org/robots.txt": robots(""), FEED: OK}
    fetcher, _, clock = make(pages, min_delay_seconds=0)
    fetcher.fetch(FEED)
    fetcher.fetch(FEED)
    assert clock.waits == [1.0, 1.0]  # the 1 s floor holds whatever the setting says
    fetcher, _, clock = make(pages, min_delay_seconds=3)
    fetcher.fetch(FEED)
    assert clock.waits == [3.0]


@pytest.mark.parametrize("bad", [-1, "1", True])
def test_bad_minimum_gap_is_refused(bad):
    with pytest.raises(ValueError):
        Fetcher(CONTACT, min_delay_seconds=bad)


@pytest.mark.parametrize(
    "text",
    [
        "User-agent: *\nCrawl-delay: 10s\nDisallow:",
        "Crawl-delay: ten\nUser-agent: *\nDisallow:",
        "User-agent: *\nCrawl-delay: -5",
        "User-agent: *\nCrawl-delay: nan",
    ],
)
def test_unreadable_crawl_delay_stops_the_site(text):
    fetcher, site, _ = make({"https://org.example.org/robots.txt": robots(text), FEED: OK})
    with pytest.raises(FetchError, match="Crawl-delay"):
        fetcher.fetch(FEED)
    with pytest.raises(FetchError, match="Crawl-delay"):
        fetcher.fetch(FEED)  # still stopped, robots.txt not read again
    assert site.urls == ["https://org.example.org/robots.txt"]


def test_unreadable_crawl_delay_for_another_bot_does_not_matter():
    text = "User-agent: OtherBot\nCrawl-delay: 10s\n\nUser-agent: *\nCrawl-delay: 2"
    fetcher, _, clock = make({"https://org.example.org/robots.txt": robots(text), FEED: OK})
    fetcher.fetch(FEED)
    assert clock.waits == [2.0]


def test_user_agent_cannot_be_changed():
    fetcher, _, _ = make({})
    with pytest.raises(AttributeError):
        fetcher.user_agent = "Mozilla/5.0"
    assert fetcher.user_agent == user_agent(CONTACT)


def test_different_sites_do_not_wait_for_each_other():
    other = "https://other.example.net/cal.ics"
    fetcher, _, clock = make(
        {
            "https://org.example.org/robots.txt": robots("Crawl-delay: 10"),
            "https://other.example.net/robots.txt": robots(""),
            FEED: OK,
            other: OK,
        }
    )
    fetcher.fetch(FEED)
    fetcher.fetch(other)
    assert clock.waits == [10.0, 1.0]


# -- turned away: stop, never retry -------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        (403, {"server": "cloudflare"}, b"<html><title>Just a moment...</title></html>"),
        (503, {"cf-mitigated": "challenge"}, b""),
        (200, {}, b"<html><script src='/cdn-cgi/challenge-platform/x.js'></script></html>"),
        (403, {}, b"Forbidden"),
        (401, {}, b""),
        (429, {"retry-after": "60"}, b""),
    ],
)
def test_turned_away_raises_blocked_after_one_try(answer):
    fetcher, site, _ = make({"https://org.example.org/robots.txt": robots(""), FEED: answer})
    with pytest.raises(Blocked):
        fetcher.fetch(FEED)
    assert site.urls.count(FEED) == 1


def test_other_http_errors_are_reported_not_retried():
    fetcher, site, _ = make(
        {"https://org.example.org/robots.txt": robots(""), FEED: (500, {}, b"")}
    )
    with pytest.raises(FetchError, match="HTTP 500"):
        fetcher.fetch(FEED)
    assert site.urls.count(FEED) == 1


@pytest.mark.parametrize(
    "url", ["ftp://org.example.org/x", "file:///etc/passwd", "org.example.org"]
)
def test_only_web_addresses(url):
    fetcher, site, _ = make({})
    with pytest.raises(FetchError):
        fetcher.fetch(url)
    assert site.urls == []


def test_text_uses_declared_charset():
    response = Response(
        FEED,
        200,
        {"content-type": "text/calendar; charset=iso-8859-1"},
        "Café".encode("iso-8859-1"),
    )
    assert response.text() == "Café"


# -- robots.txt reader --------------------------------------------------------


def rules(text: str) -> RobotsRules:
    return RobotsRules.parse(text, BOT_NAME)


def test_group_naming_our_bot_wins_over_star():
    text = "User-agent: *\nDisallow: /\n\nUser-agent: CitywideVolunteerHubBot\nDisallow: /private/"
    r = rules(text)
    assert r.allowed("https://x.org/events/")
    assert not r.allowed("https://x.org/private/a")


def test_groups_for_other_bots_do_not_apply():
    text = "User-agent: ClaudeBot\nUser-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nDisallow: /wp-admin/"
    r = rules(text)
    assert r.allowed("https://x.org/events/?ical=1")
    assert not r.allowed("https://x.org/wp-admin/x")


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("/events/category/volunteer/list/?ical=1", True),
        ("/?s=trees", False),  # *s=*
        ("/news/feed/", False),  # */feed/*
        ("/my-account/orders", False),  # /my-account/*
        ("/wp-login.php", False),  # /*wp-login.php*
        ("/page.pdf", False),  # /*.pdf$
        ("/page.pdf?x=1", True),
    ],
)
def test_wildcards_and_end_anchor(path, allowed):
    text = """
User-agent: *
Crawl-delay: 5
Disallow: *s=*
Disallow: */feed/*
Disallow: /my-account/*
Disallow: /*wp-login.php*
Disallow: /*.pdf$
"""
    assert rules(text).allowed("https://x.org" + path) is allowed


def test_longest_rule_wins_and_allow_wins_ties():
    text = "User-agent: *\nDisallow: /events/\nAllow: /events/list/\nDisallow: /a\nAllow: /a"
    r = rules(text)
    assert r.allowed("https://x.org/events/list/?ical=1")
    assert not r.allowed("https://x.org/events/other")
    assert r.allowed("https://x.org/a")


def test_empty_disallow_allows_everything():
    assert rules("User-agent: *\nDisallow:").allowed("https://x.org/anything")


# Read-only facts for the run report: robots.txt read when, and the delay used.


def test_robots_check_and_delay_are_reported():
    from datetime import UTC, datetime

    from pvscrapers.fetch import Fetcher, Response

    def transport(url, headers, timeout, max_bytes):
        if url.endswith("/robots.txt"):
            return Response(url, 200, {}, b"User-agent: *\nCrawl-delay: 7\n")
        return Response(url, 200, {}, b"ok")

    when = datetime(2026, 10, 18, 18, 39, tzinfo=UTC)
    fetcher = Fetcher(
        "bot@example.org", transport=transport, sleep=lambda s: None, wall_clock=lambda: when
    )
    page = "https://site.example.org/cal"
    assert fetcher.robots_check(page) is None
    fetcher.fetch(page)
    check = fetcher.robots_check(page)
    assert (check.url, check.read_at, check.status) == (
        "https://site.example.org/robots.txt",
        when,
        200,
    )
    assert fetcher.delay_seconds(page) == 7
    assert fetcher.delay_seconds(page, extra_delay_seconds=10) == 10


def test_missing_robots_is_reported_with_its_status_and_the_floor():
    from pvscrapers.fetch import FLOOR_DELAY_SECONDS, Fetcher, Response

    def transport(url, headers, timeout, max_bytes):
        status = 404 if url.endswith("/robots.txt") else 200
        return Response(url, status, {}, b"")

    fetcher = Fetcher("bot@example.org", transport=transport, sleep=lambda s: None)
    fetcher.fetch("https://site.example.org/cal")
    assert fetcher.robots_check("https://site.example.org/x").status == 404
    assert fetcher.delay_seconds("https://site.example.org/x") == FLOOR_DELAY_SECONDS
