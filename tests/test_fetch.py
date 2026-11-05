"""The polite fetcher and the robots.txt reader (PROJECT.md section 4, rule 1).

No network: a fake transport answers every request and records it, and a
fake clock records every wait.
"""

from __future__ import annotations

import json

import pytest

from pvscrapers import __version__
from pvscrapers import fetch as fetch_module
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


# -- python -m pvscrapers.fetch: one polite fetch by hand (Q48) ---------------


@pytest.fixture(autouse=True)
def _own_cache(tmp_path, monkeypatch):
    """The command's default state file goes to a test folder, never ~/.cache."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))


PAGE = "https://org.example.org/volunteer/"
ROBOTS = "https://org.example.org/robots.txt"


def _cli(pages, argv, capsys):
    site, waits = FakeSite(pages), []
    code = fetch_module.main(argv, transport=site, sleep=waits.append)
    return code, site, waits, capsys.readouterr()


def test_command_fetches_through_robots_and_saves_the_page(tmp_path, capsys):
    out = tmp_path / "page.html"
    pages = {ROBOTS: (200, {}, b"User-agent: *\nCrawl-delay: 5\n"), PAGE: (200, {}, b"<p>hi</p>")}
    code, site, waits, shown = _cli(pages, [PAGE, "--contact", CONTACT, "--out", str(out)], capsys)
    assert code == 0
    assert site.urls == [ROBOTS, PAGE]  # robots.txt first
    assert all(h["User-Agent"] == user_agent(CONTACT) for _, h in site.requests)
    assert waits and waits[0] > 4  # the site's Crawl-delay is kept between the two
    assert out.read_bytes() == b"<p>hi</p>"
    assert f"HTTP 200 {PAGE}: 9 bytes, saved to {out}" in shown.err
    assert "Crawl-delay" not in shown.err and "delay 5 s" in shown.err
    assert shown.out == ""


def test_command_reads_contact_from_settings(tmp_path, capsys):
    settings = tmp_path / "site.json"
    settings.write_text(json.dumps({"site": {"contact_email": CONTACT}}))
    pages = {ROBOTS: (404, {}, b""), PAGE: (200, {}, b"ok")}
    code, site, _, shown = _cli(
        pages, [PAGE, "--settings", str(settings), "--out", str(tmp_path / "o")], capsys
    )
    assert code == 0
    assert CONTACT in site.requests[0][1]["User-Agent"]
    assert "HTTP 404, none, so all allowed" in shown.err


def test_command_reads_yaml_settings_when_pyyaml_is_there(tmp_path, capsys):
    pytest.importorskip("yaml")
    settings = tmp_path / "site.yml"
    settings.write_text(f"site:\n  contact_email: {CONTACT}\n")
    pages = {ROBOTS: (404, {}, b""), PAGE: (200, {}, b"ok")}
    code, *_ = _cli(
        pages, [PAGE, "--settings", str(settings), "--out", str(tmp_path / "o")], capsys
    )
    assert code == 0


def test_command_refuses_a_disallowed_address(tmp_path, capsys):
    out = tmp_path / "page.html"
    pages = {ROBOTS: (200, {}, b"User-agent: *\nDisallow: /volunteer/\n"), PAGE: (200, {}, b"x")}
    code, site, _, shown = _cli(pages, [PAGE, "--contact", CONTACT, "--out", str(out)], capsys)
    assert code == fetch_module.EXIT_DISALLOWED == 3
    assert site.urls == [ROBOTS]  # the page itself is never asked for
    assert not out.exists()
    assert f"REFUSED: robots.txt disallows {PAGE} for {BOT_NAME}" in shown.err


def test_command_checks_robots_for_every_redirect(tmp_path, capsys):
    other = "https://other.example.org/private/page"
    pages = {
        ROBOTS: (404, {}, b""),
        PAGE: (301, {"location": other}, b""),
        "https://other.example.org/robots.txt": (200, {}, b"User-agent: *\nDisallow: /private/\n"),
        other: (200, {}, b"secret"),
    }
    code, site, _, shown = _cli(pages, [PAGE, "--contact", CONTACT], capsys)
    assert code == 3
    assert other not in site.urls
    assert "https://other.example.org/robots.txt" in site.urls
    assert f"REFUSED: robots.txt disallows {other}" in shown.err


def test_command_stops_when_the_site_turns_the_bot_away(capsys):
    pages = {ROBOTS: (404, {}, b""), PAGE: (403, {}, b"no")}
    code, site, _, shown = _cli(pages, [PAGE, "--contact", CONTACT], capsys)
    assert code == fetch_module.EXIT_BLOCKED
    assert site.urls == [ROBOTS, PAGE]  # no retry
    assert "BLOCKED" in shown.err and "Do not retry" in shown.err


def test_command_reports_a_failed_fetch(capsys):
    pages = {ROBOTS: (404, {}, b"")}
    code, _, _, shown = _cli(pages, [PAGE, "--contact", CONTACT], capsys)
    assert code == fetch_module.EXIT_FAILED
    assert f"FAILED: {PAGE}: HTTP 404" in shown.err


def test_command_needs_a_real_contact_address(tmp_path, capsys):
    code, site, _, shown = _cli({}, [PAGE, "--contact", "not-an-address"], capsys)
    assert code == fetch_module.EXIT_USAGE
    assert site.urls == []
    settings = tmp_path / "site.json"
    settings.write_text('{"site": {}}')
    code, site, _, shown = _cli({}, [PAGE, "--settings", str(settings)], capsys)
    assert code == 2 and site.urls == [] and "no site.contact_email" in shown.err


def test_command_writes_to_standard_output_without_out(capsysbinary):
    pages = {ROBOTS: (404, {}, b""), PAGE: (200, {}, b"<p>body</p>")}
    code = fetch_module.main(
        [PAGE, "--contact", CONTACT], transport=FakeSite(pages), sleep=lambda s: None
    )
    shown = capsysbinary.readouterr()
    assert code == 0
    assert shown.out == b"<p>body</p>"
    assert b"saved to standard output" in shown.err


# -- licence gate follow-up: waits across commands, several addresses, blocks --

PAGE2 = "https://org.example.org/volunteer/shifts/"
OTHER = "https://other.example.org/page"


class WallClock(FakeClock):
    """A fake wall clock shared by several commands; sleeping moves it on."""

    def __init__(self):
        super().__init__()
        self.now = 1_800_000_000.0


def _run(pages, argv, clock, site=None):
    site = site or FakeSite(pages)
    code = fetch_module.main(argv, transport=site, sleep=clock.sleep, clock=clock)
    return code, site


def test_two_commands_in_a_row_keep_the_crawl_delay(tmp_path):
    clock, state = WallClock(), tmp_path / "state.json"
    pages = {ROBOTS: (200, {}, b"User-agent: *\nCrawl-delay: 3\n"), PAGE: OK, PAGE2: OK}
    base = ["--contact", CONTACT, "--state", str(state)]
    code, _ = _run(pages, [PAGE, *base, "--out", str(tmp_path / "a")], clock)
    assert code == 0 and clock.waits == [3.0]  # robots.txt, wait, the page
    clock.now += 0.09  # the next command starts right away
    code, site = _run(pages, [PAGE2, *base, "--out", str(tmp_path / "b")], clock)
    assert code == 0
    assert site.urls == [ROBOTS, PAGE2]
    assert clock.waits[1] == 2.91  # before its robots.txt: the rest of the 3 s
    assert clock.waits[2] == 3.0  # and again before the page
    saved = json.loads(state.read_text())
    assert set(saved) == {"https://org.example.org"}  # site addresses and times only
    assert saved["https://org.example.org"]["delay_seconds"] == 3.0


def test_two_commands_in_a_row_keep_the_one_second_floor(tmp_path):
    clock, state = WallClock(), tmp_path / "state.json"
    pages = {ROBOTS: (404, {}, b""), PAGE: OK}
    argv = [PAGE, "--contact", CONTACT, "--state", str(state), "--out", str(tmp_path / "p")]
    _run(pages, argv, clock)
    clock.now += 0.2
    _run(pages, argv, clock)
    assert clock.waits == [1.0, 0.8, 1.0]


def test_default_state_file_is_in_the_cache_folder(tmp_path):
    clock = WallClock()
    pages = {ROBOTS: (404, {}, b""), PAGE: OK}
    _run(pages, [PAGE, "--contact", CONTACT, "--out", str(tmp_path / "p")], clock)
    assert (tmp_path / "cache" / "pvscrapers" / "last-request.json").is_file()


def test_one_command_fetches_a_sites_pages_in_turn(tmp_path):
    clock, out = WallClock(), tmp_path / "pages"
    pages = {
        ROBOTS: (200, {}, b"User-agent: *\nCrawl-delay: 2\n"),
        PAGE: (200, {}, b"one"),
        PAGE2: (200, {}, b"two"),
    }
    argv = [PAGE, PAGE2, "--contact", CONTACT, "--out-dir", str(out)]
    code, site = _run(pages, argv, clock)
    assert code == 0
    assert site.urls == [ROBOTS, PAGE, PAGE2]  # robots.txt read once
    assert clock.waits == [2.0, 2.0]
    files = sorted(f for f in out.iterdir() if not f.name.endswith(".fetch.json"))
    assert [f.read_bytes() for f in files] == [b"one", b"two"]
    assert files[0].name == "01-org-example-org-volunteer"
    assert (out / "01-org-example-org-volunteer.fetch.json").is_file()  # one record per page


def test_several_addresses_need_an_out_dir(tmp_path, capsys):
    code, site = _run({}, [PAGE, PAGE2, "--contact", CONTACT], WallClock())
    assert code == 2 and site.urls == []
    assert "need --out-dir" in capsys.readouterr().err


@pytest.mark.parametrize("status", [401, 403, 429])
def test_robots_txt_turning_the_bot_away_blocks_the_whole_site(tmp_path, capsys, status):
    clock = WallClock()
    pages = {
        ROBOTS: (status, {}, b"Access Denied"),
        PAGE: OK,
        PAGE2: OK,
        "https://other.example.org/robots.txt": (404, {}, b""),
        OTHER: OK,
    }
    argv = [PAGE, PAGE2, OTHER, "--contact", CONTACT, "--out-dir", str(tmp_path / "o")]
    code, site = _run(pages, argv, clock)
    assert code == fetch_module.EXIT_BLOCKED == 4
    assert site.urls.count(ROBOTS) == 1  # asked once; then nothing more from that site
    assert PAGE not in site.urls and PAGE2 not in site.urls
    assert OTHER in site.urls  # another site is still fetched
    err = capsys.readouterr().err
    assert err.count("BLOCKED") == 2 and "Nothing more is asked of this site" in err


@pytest.mark.parametrize("status", [404, 410])
def test_robots_txt_missing_still_allows_fetching(status):
    fetcher, _, _ = make({"https://org.example.org/robots.txt": (status, {}, b""), FEED: OK})
    assert fetcher.fetch(FEED).status == 200


def test_scraper_fetcher_asks_a_blocked_site_nothing_more():
    """Scraper runs share one Fetcher: a second source on a site that turned the bot
    away is blocked without another request."""
    second = "https://org.example.org/other-feed/?ical=1"
    fetcher, site, _ = make({"https://org.example.org/robots.txt": (403, {}, b"no"), FEED: OK})
    with pytest.raises(Blocked):
        fetcher.fetch(FEED)
    with pytest.raises(Blocked, match="nothing more is asked of this site this run"):
        fetcher.fetch(second)
    assert site.urls == ["https://org.example.org/robots.txt"]


def test_page_turning_the_bot_away_blocks_the_rest_of_the_site():
    second = "https://org.example.org/other-feed/?ical=1"
    fetcher, site, _ = make(
        {"https://org.example.org/robots.txt": robots(""), FEED: (429, {}, b""), second: OK}
    )
    with pytest.raises(Blocked):
        fetcher.fetch(FEED)
    with pytest.raises(Blocked):
        fetcher.fetch(second)
    assert second not in site.urls


# -- a blocked site is remembered for 24 hours across commands (owner, licence note 1) --


def _blocking_pages():
    return {
        ROBOTS: (404, {}, b""),
        PAGE: (403, {}, b"Access Denied"),
        PAGE2: OK,
        "https://other.example.org/robots.txt": (404, {}, b""),
        OTHER: OK,
    }


def test_blocked_site_is_remembered_across_commands(tmp_path, capsys):
    clock, state = WallClock(), tmp_path / "state.json"
    base = ["--contact", CONTACT, "--state", str(state)]
    code, _ = _run(_blocking_pages(), [PAGE, *base, "--out", str(tmp_path / "a")], clock)
    assert code == 4
    saved = json.loads(state.read_text())
    entry = saved["https://org.example.org"]
    assert entry["blocked_at"] == clock.now
    assert set(entry) <= {"last_request", "delay_seconds", "blocked_at"}  # times only
    assert "Access Denied" not in state.read_text() and "403" not in state.read_text()
    capsys.readouterr()

    clock.now += 3600  # an hour later, another command
    code, site = _run(_blocking_pages(), [PAGE2, *base, "--out", str(tmp_path / "b")], clock)
    assert code == fetch_module.EXIT_BLOCKED
    assert site.urls == []  # refused without a request, robots.txt included
    err = capsys.readouterr().err
    blocked_at = fetch_module._local_time(clock.now - 3600)
    after = fetch_module._local_time(clock.now - 3600 + 86_400)
    assert f"BLOCKED: {PAGE2}: blocked at {blocked_at}; try again after {after}" in err


def test_remembered_block_expires_after_24_hours(tmp_path):
    clock, state = WallClock(), tmp_path / "state.json"
    base = ["--contact", CONTACT, "--state", str(state)]
    _run(_blocking_pages(), [PAGE, *base, "--out", str(tmp_path / "a")], clock)
    clock.now += 86_400 - 1
    code, site = _run(_blocking_pages(), [PAGE2, *base, "--out", str(tmp_path / "b")], clock)
    assert code == 4 and site.urls == []  # one second short of a day: still refused
    clock.now += 1
    code, site = _run(_blocking_pages(), [PAGE2, *base, "--out", str(tmp_path / "c")], clock)
    assert code == 0
    assert site.urls == [ROBOTS, PAGE2]
    assert "blocked_at" not in json.loads(state.read_text())["https://org.example.org"]


def test_remembered_block_leaves_other_sites_alone(tmp_path):
    clock, state = WallClock(), tmp_path / "state.json"
    base = ["--contact", CONTACT, "--state", str(state)]
    _run(_blocking_pages(), [PAGE, *base, "--out", str(tmp_path / "a")], clock)
    clock.now += 60
    argv = [PAGE2, OTHER, *base, "--out-dir", str(tmp_path / "o")]
    code, site = _run(_blocking_pages(), argv, clock)
    assert code == 4  # the highest exit of the two
    assert site.urls == ["https://other.example.org/robots.txt", OTHER]
    assert (tmp_path / "o" / "02-other-example-org-page").read_bytes() == CALENDAR


def test_scraper_fetcher_ignores_the_command_state_file(tmp_path):
    """A Fetcher made without carry_over (as scheduled scraper runs make it) knows
    nothing of a block remembered by the command line."""
    clock, state = WallClock(), tmp_path / "state.json"
    _run(_blocking_pages(), [PAGE, "--contact", CONTACT, "--state", str(state)], clock)
    fetcher, _, _ = make({ROBOTS: (404, {}, b""), PAGE2: OK})
    assert fetcher.fetch(PAGE2).status == 200


# -- the fetch record beside each saved page (licence gate: recorder proof) ------


def test_saved_page_gets_a_fetch_record(tmp_path):
    clock = WallClock()
    out = tmp_path / "page.html"
    pages = {
        ROBOTS: (200, {}, b"User-agent: *\nCrawl-delay: 2\n"),
        PAGE: (301, {"location": PAGE2}, b""),
        PAGE2: (200, {}, b"<p>hi</p>"),
    }
    argv = [PAGE, "--contact", CONTACT, "--out", str(out), "--crawl-delay", "5"]
    code, _ = _run(pages, argv, clock)
    assert code == 0
    record = json.loads((tmp_path / "page.html.fetch.json").read_text())
    assert record["url"] == PAGE and record["final_url"] == PAGE2 and record["status"] == 200
    assert record["bot"] == f"{BOT_NAME}/{__version__}"
    assert record["robots_txt"]["status"] == 200 and record["robots_txt"]["verdict"] == "allowed"
    assert record["delay_seconds"] == 5.0 and record["source_crawl_delay_seconds"] == 5.0
    assert clock.waits == [5.0, 5.0]  # the source's own delay was kept
    assert record["fetched_at"] == fetch_module._iso(clock.now)
    assert record["robots_txt"]["read_at"] <= record["fetched_at"]
    assert CONTACT not in json.dumps(record)  # never the contact address


def test_no_fetch_record_for_standard_output(tmp_path, capsysbinary):
    pages = {ROBOTS: (404, {}, b""), PAGE: OK}
    code, _ = _run(pages, [PAGE, "--contact", CONTACT], WallClock())
    assert code == 0
    assert not list(tmp_path.glob("**/*.fetch.json"))


def test_negative_crawl_delay_is_refused(tmp_path):
    code, site = _run({}, [PAGE, "--contact", CONTACT, "--crawl-delay", "-1"], WallClock())
    assert code == 2 and site.urls == []
