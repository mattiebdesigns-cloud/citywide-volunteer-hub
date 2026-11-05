"""The polite fetcher: the only part of the package that touches the network.

What it promises (README ground rules 1 and 2):

- It reads a site's robots.txt before any other request to that site, and
  never fetches an address robots.txt disallows for our bot.
- It identifies itself as `CitywideVolunteerHubBot/<version> (+mailto:<contact>)`.
  The contact address comes from the city's settings; this code holds none.
  There is no way to send any other User-Agent, so it can never pose as a
  browser or as another crawler.
- One request at a time. Between two requests to the same site it waits the
  longest of: 1 second (the project's floor, which no setting can lower),
  the fetcher's `min_delay_seconds` if higher, the site's robots.txt
  Crawl-delay, and the source entry's `crawl_delay_seconds`. A Crawl-delay it cannot read
  stops that site and is reported; it never guesses a delay.
- When a site turns the bot away (a Cloudflare challenge, HTTP 401, 403 or
  429, on robots.txt or on a page) it stops and raises `Blocked`. It never
  retries, never tries another way in, and asks that site for nothing more
  for the rest of the run. Only a 404 or another 4xx on robots.txt means the
  site has none. A robots.txt that cannot be read (server error, network
  failure) also stops the source, as RFC 9309 asks.
- No retries at all: a failed fetch is reported, and the next scheduled run tries again.

Fetching one address by hand (research reads, PROJECT.md 4.1), through this
same fetcher:

    python -m pvscrapers.fetch <url> [<url> ...] --settings <site.yml or .json> --out-dir DIR
    python -m pvscrapers.fetch <url> --contact <email> [--out FILE]

Give all of a site's addresses in one command: one fetcher handles them in
turn. robots.txt is checked for each address and for every redirect, with our
bot's name and the contact address from the settings. Between two requests to
one site it waits the site's Crawl-delay, and never less than 1 second, also
across commands: each site's last request time and delay are kept in a small
file (--state, default ~/.cache/pvscrapers/last-request.json; it holds site
addresses and times only). A site that turns the bot away is remembered in
the same file for 24 hours: every command refuses it without a request
("blocked at <time>; try again after <time>"). Scheduled scraper runs do not
read this file: each run makes its own Fetcher, which stops asking a site that
turned it away for the rest of that run only. What happened goes to the screen (standard error);
pages go to --out-dir (one file per address), to --out (one address), or to
standard output (one address, neither given). Beside each page saved to a
file it writes `<file>.fetch.json`, the proof of how it was fetched: the
address asked, the final address after redirects, the HTTP status, when, the
bot's name and version (never the contact address), when robots.txt was read
and its answer, and the wait kept. `--crawl-delay SECONDS` adds a source's own
delay on top of the site's (as a source entry's crawl_delay_seconds does). Exit codes: 0 fetched; 1 the fetch
failed (an HTTP error, the network); 2 a usage or settings problem; 3 robots.txt
disallows an address (nothing fetched from it); 4 a site turned the bot away
(robots.txt or a page answered 401, 403, 429 or a challenge; nothing more is
asked of that site). With several addresses, the highest of these is returned. Reading YAML settings needs PyYAML, which the private repo's environment
has; this package itself still uses the standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from pvscrapers import __version__
from pvscrapers.robots import RobotsRules

BOT_NAME = "CitywideVolunteerHubBot"
FLOOR_DELAY_SECONDS = 1.0  # never wait less than this between requests to one site
BLOCK_SECONDS = 86_400  # the command line remembers a site that turned the bot away this long
_EMAIL = re.compile(r"^[^@\s()<>]+@[^@\s()<>]+\.[^@\s()<>]+$")
_REDIRECTS = {301, 302, 303, 307, 308}


class FetchError(Exception):
    """A page could not be fetched. The source is skipped for this run and reported."""

    def __init__(self, url: str, reason: str):
        super().__init__(f"{url}: {reason}")
        self.url = url
        self.reason = reason


class Blocked(FetchError):
    """The site turned our bot away. Stop; never retry or work around it."""


class DisallowedByRobots(FetchError):
    """robots.txt does not allow our bot to fetch this address."""


@dataclass
class Response:
    url: str
    status: int
    headers: dict[str, str]  # names in lower case
    body: bytes

    def text(self) -> str:
        message = Message()
        message["content-type"] = self.headers.get("content-type", "")
        charset = message.get_content_charset() or "utf-8"
        try:
            return self.body.decode(charset)
        except (LookupError, UnicodeDecodeError):
            return self.body.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class RobotsCheck:
    """When and how a site's robots.txt was read, for the run report. Read-only."""

    url: str  # the robots.txt address finally read (after redirects)
    read_at: datetime  # wall-clock time, UTC
    status: int  # 200: rules found; 4xx: no robots.txt, so everything is allowed (RFC 9309)


# A transport sends one GET request and returns the response without following
# redirects. Tests pass in a fake one, so they never touch the network.
Transport = Callable[[str, dict[str, str], float, int], Response]


def user_agent(contact_email: str) -> str:
    """The User-Agent for every request: our bot's name, version and contact address."""
    contact = (contact_email or "").strip()
    if not _EMAIL.match(contact):
        raise ValueError("a contact email address from the city's settings is required")
    return f"{BOT_NAME}/{__version__} (+mailto:{contact})"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # the fetcher follows redirects itself, checking robots.txt each time


def urllib_transport(url: str, headers: dict[str, str], timeout: float, max_bytes: int) -> Response:
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        response = error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise FetchError(url, f"network error ({error})") from error
    with response:
        body = response.read(max_bytes + 1)
        status = response.status if hasattr(response, "status") else response.code
        found = {k.lower(): v for k, v in response.headers.items()}
    if len(body) > max_bytes:
        raise FetchError(url, f"page is larger than {max_bytes} bytes")
    return Response(url=url, status=status, headers=found, body=body)


def _cloudflare_challenge(response: Response) -> bool:
    if response.headers.get("cf-mitigated", "").lower() == "challenge":
        return True
    if response.status in (403, 503) and "cloudflare" in response.headers.get("server", "").lower():
        return True
    head = response.body[:4096].lower()
    return b"challenge-platform" in head or b"<title>just a moment" in head


def _local_time(seconds: float) -> str:
    try:
        return datetime.fromtimestamp(seconds, UTC).astimezone().isoformat(timespec="minutes")
    except (OverflowError, OSError, ValueError):
        return f"{seconds:.0f}"


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


@dataclass
class Fetcher:
    """Fetches pages for one run. Create one per run and reuse it for every source."""

    contact_email: str
    transport: Transport = urllib_transport
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    min_delay_seconds: float = 1.0
    timeout_seconds: float = 30.0
    max_bytes: int = 5_000_000
    max_redirects: int = 5
    wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    _robots: dict[str, RobotsRules] = field(default_factory=dict, init=False, repr=False)
    _robots_checked: dict[str, RobotsCheck] = field(default_factory=dict, init=False, repr=False)
    _last_request: dict[str, float] = field(default_factory=dict, init=False, repr=False)
    _user_agent: str = field(default="", init=False, repr=False)
    _blocked: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _blocked_at: dict[str, float] = field(default_factory=dict, init=False, repr=False)
    _carried_delay: dict[str, float] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._user_agent = user_agent(self.contact_email)
        for name in ("min_delay_seconds", "timeout_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"{name} must be a number of seconds, 0 or more")

    @property
    def user_agent(self) -> str:
        """Fixed when the fetcher is made; it cannot be changed afterwards."""
        return self._user_agent

    @classmethod
    def from_settings(cls, settings: dict, **options) -> Fetcher:
        """Build a fetcher from a city's settings (its `site.contact_email`)."""
        contact = ((settings or {}).get("site") or {}).get("contact_email") or ""
        return cls(contact_email=contact, **options)

    # -- public -------------------------------------------------------------

    def fetch_source(self, source: dict) -> Response:
        """Fetch a source entry's `url`, honouring its `crawl_delay_seconds`."""
        delay = source.get("crawl_delay_seconds") or 0
        if isinstance(delay, bool) or not isinstance(delay, (int, float)) or delay < 0:
            raise ValueError(f"source {source.get('id', '?')!r}: crawl_delay_seconds must be >= 0")
        return self.fetch(source["url"], extra_delay_seconds=float(delay))

    def fetch(self, url: str, *, extra_delay_seconds: float = 0.0) -> Response:
        """GET one address politely. Raises FetchError (or Blocked) on any failure."""
        for _ in range(self.max_redirects + 1):
            self._check_scheme(url)
            origin = _origin(url)
            if origin in self._blocked:
                raise Blocked(url, self._blocked[origin])
            rules = self._robots_for(origin, extra_delay_seconds)
            self._check_crawl_delay(url, rules)
            if not rules.allowed(url):
                raise DisallowedByRobots(url, "robots.txt disallows this address for our bot")
            response = self._request(url, origin, extra_delay_seconds)
            if response.status in _REDIRECTS and response.headers.get("location"):
                url = urljoin(url, response.headers["location"])
                continue
            self._raise_if_refused(response)
            if response.status != 200:
                raise FetchError(url, f"HTTP {response.status}")
            return response
        raise FetchError(url, f"more than {self.max_redirects} redirects")

    def robots_rules(self, url: str) -> RobotsRules | None:
        """The robots.txt rules already read for this address's site, if any."""
        return self._robots.get(_origin(url))

    def robots_check(self, url: str) -> RobotsCheck | None:
        """When and how this address's site robots.txt was read this run, if it was."""
        return self._robots_checked.get(_origin(url))

    def delay_seconds(self, url: str, *, extra_delay_seconds: float = 0.0) -> float:
        """The gap this fetcher keeps between two requests to this address's site."""
        return self._gap(_origin(url), extra_delay_seconds)

    def carry_over(self, last_requests: dict[str, dict]) -> None:
        """Waits from an earlier run of this fetcher (the command line keeps them in a
        file): {site: {"last_request": <clock time>, "delay_seconds": <gap>,
        "blocked_at": <clock time, if it turned the bot away>}}. A site blocked less
        than BLOCK_SECONDS ago is refused without a request. Use it only with a wall
        clock (time.time), so times from another process compare."""
        now = self.clock()
        for origin, entry in last_requests.items():
            if not isinstance(entry, dict):
                continue
            blocked_at = entry.get("blocked_at")
            if (
                isinstance(blocked_at, (int, float))
                and not isinstance(blocked_at, bool)
                and 0 <= now - blocked_at < BLOCK_SECONDS
            ):
                key = origin.lower()
                self._blocked_at[key] = float(blocked_at)
                self._blocked[key] = (
                    f"blocked at {_local_time(blocked_at)}; try again after "
                    f"{_local_time(blocked_at + BLOCK_SECONDS)}"
                )
            try:
                at = float(entry["last_request"])
                delay = float(entry["delay_seconds"])
            except (KeyError, TypeError, ValueError):
                continue
            key = origin.lower()
            if at > self._last_request.get(key, float("-inf")):
                self._last_request[key] = at
                self._carried_delay[key] = max(delay, 0.0)

    def last_requests(self) -> dict[str, dict]:
        """Each site asked this run: when, the gap kept, and when it turned the bot away
        (for carry_over). Site addresses and times only."""
        found: dict[str, dict] = {}
        for origin in set(self._last_request) | set(self._blocked_at):
            entry: dict = {"delay_seconds": self._gap(origin, 0.0)}
            if origin in self._last_request:
                entry["last_request"] = self._last_request[origin]
            if origin in self._blocked_at:
                entry["blocked_at"] = self._blocked_at[origin]
            found[origin] = entry
        return found

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _check_scheme(url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise FetchError(url, "only http and https addresses can be fetched")

    def _robots_for(self, origin: str, extra_delay: float) -> RobotsRules:
        if origin in self._robots:
            return self._robots[origin]
        url = origin + "/robots.txt"
        for _ in range(self.max_redirects + 1):
            response = self._request(url, origin, extra_delay)
            if response.status in _REDIRECTS and response.headers.get("location"):
                url = urljoin(url, response.headers["location"])
                self._check_scheme(url)
                continue
            break
        else:
            raise FetchError(url, "robots.txt redirects too many times")

        self._raise_if_refused(response)
        if response.status == 200:
            rules = RobotsRules.parse(response.text(), BOT_NAME)
        elif 400 <= response.status < 500:
            rules = RobotsRules.allowing_everything()  # no robots.txt: RFC 9309 allows all
        else:
            raise FetchError(url, f"robots.txt could not be read (HTTP {response.status})")
        self._robots[origin] = rules
        self._robots_checked[origin] = RobotsCheck(url, self.wall_clock(), response.status)
        self._carried_delay.pop(origin, None)  # this run's robots.txt decides from now on
        return rules

    @staticmethod
    def _check_crawl_delay(url: str, rules: RobotsRules) -> None:
        if rules.unreadable_crawl_delay is not None:
            raise FetchError(
                url,
                f"robots.txt Crawl-delay {rules.unreadable_crawl_delay!r} could not be read; "
                "this site is skipped rather than guess a delay",
            )

    def _raise_if_refused(self, response: Response) -> None:
        reason = None
        if _cloudflare_challenge(response):
            reason = "Cloudflare challenge; our bot is not let in"
        elif response.status in (401, 403):
            reason = f"HTTP {response.status}; our bot is not let in"
        elif response.status == 429:
            reason = "HTTP 429; the site asks us to slow down"
        if reason is not None:
            origin = _origin(response.url)
            self._blocked_at[origin] = self.clock()
            self._blocked[origin] = f"{reason}; nothing more is asked of this site this run"
            raise Blocked(response.url, reason)

    def _gap(self, origin: str, extra_delay: float) -> float:
        rules = self._robots.get(origin)
        site_delay = rules.crawl_delay if rules and rules.crawl_delay else 0.0
        carried = self._carried_delay.get(origin, 0.0)  # from an earlier command
        return max(FLOOR_DELAY_SECONDS, self.min_delay_seconds, site_delay, extra_delay, carried)

    def _request(self, url: str, origin: str, extra_delay: float) -> Response:
        last = self._last_request.get(origin)
        if last is not None:
            wait = last + self._gap(origin, extra_delay) - self.clock()
            if wait > 0:
                self.sleep(wait)
        headers = {"User-Agent": self.user_agent, "Accept": "*/*", "Accept-Encoding": "identity"}
        try:
            return self.transport(url, headers, self.timeout_seconds, self.max_bytes)
        finally:
            self._last_request[origin] = self.clock()


# -- command line: fetch one address by hand ---------------------------------

EXIT_OK, EXIT_FAILED, EXIT_USAGE, EXIT_DISALLOWED, EXIT_BLOCKED = 0, 1, 2, 3, 4


def _contact_from_settings(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        settings = json.loads(text)
    else:
        try:
            import yaml  # optional; the private repo's environment has it (MIT)
        except ImportError:
            raise ValueError(
                "reading YAML settings needs PyYAML: run this from the private repo's "
                "environment, or pass --contact"
            ) from None
        settings = yaml.safe_load(text)
    contact = ((settings or {}).get("site") or {}).get("contact_email")
    if not contact:
        raise ValueError(f"{path} has no site.contact_email")
    return str(contact)


STATE_KEEP_SECONDS = BLOCK_SECONDS  # older entries in the state file are dropped


def default_state_file() -> Path:
    import os

    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "pvscrapers" / "last-request.json"


def _read_state(path: Path) -> dict[str, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}


def _write_state(path: Path, entries: dict[str, dict], now: float) -> None:
    def newest(entry: dict) -> float:
        times = [entry.get(k) for k in ("last_request", "blocked_at")]
        return max((t for t in times if isinstance(t, (int, float))), default=float("-inf"))

    keep = {
        k: {f: v[f] for f in ("last_request", "delay_seconds", "blocked_at") if f in v}
        for k, v in entries.items()
        if now - newest(v) < STATE_KEEP_SECONDS
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(json.dumps(keep, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


SIDECAR_SUFFIX = ".fetch.json"


def _iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, UTC).isoformat(timespec="seconds")


def fetch_record(fetcher: Fetcher, asked: str, response: Response, crawl_delay: float) -> dict:
    """How one page was fetched, for the file beside it. No contact address."""
    origin = _origin(response.url)
    check = fetcher.robots_check(response.url)
    return {
        "url": asked,
        "final_url": response.url,
        "status": response.status,
        "fetched_at": _iso(fetcher.last_requests()[origin]["last_request"]),
        "bot": f"{BOT_NAME}/{__version__}",
        "robots_txt": {
            "url": check.url if check else None,
            "read_at": check.read_at.isoformat(timespec="seconds") if check else None,
            "status": check.status if check else None,
            "verdict": "allowed",  # a disallowed address is never fetched
        },
        "delay_seconds": fetcher.delay_seconds(response.url, extra_delay_seconds=crawl_delay),
        "source_crawl_delay_seconds": crawl_delay,
        "how": "python -m pvscrapers.fetch",
    }


def _file_name(index: int, url: str) -> str:
    parts = urlsplit(url)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", f"{parts.netloc}{parts.path}").strip("-")
    return f"{index:02d}-{slug[:80] or 'page'}"


def main(
    argv: list[str] | None = None,
    *,
    transport: Transport | None = None,
    sleep: Callable[[float], None] | None = None,
    clock: Callable[[], float] | None = None,
) -> int:
    """`python -m pvscrapers.fetch <url> ...`: polite fetches by hand; see the module notes."""
    parser = argparse.ArgumentParser(
        prog="python -m pvscrapers.fetch",
        description="Fetch addresses politely: robots.txt first, our named bot, Crawl-delay.",
    )
    parser.add_argument("urls", nargs="+", metavar="url")
    who = parser.add_mutually_exclusive_group(required=True)
    who.add_argument("--settings", type=Path, help="the city's site.yml (or a .json copy)")
    who.add_argument("--contact", help="the contact email address for the User-Agent")
    where = parser.add_mutually_exclusive_group()
    where.add_argument("--out", type=Path, help="save the page here (one address only)")
    where.add_argument("--out-dir", type=Path, help="save each page in this folder")
    parser.add_argument(
        "--crawl-delay",
        type=float,
        default=0.0,
        help="a source's own crawl_delay_seconds, kept on top of the site's Crawl-delay",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=None,
        help="file keeping each site's last request time (default "
        "~/.cache/pvscrapers/last-request.json)",
    )
    args = parser.parse_args(argv)
    err = sys.stderr
    if args.crawl_delay < 0:
        print("Stopped: --crawl-delay must be 0 or more seconds.", file=err)
        return EXIT_USAGE
    if len(args.urls) > 1 and not args.out_dir:
        print("Stopped: several addresses need --out-dir (one file per address).", file=err)
        return EXIT_USAGE
    state_path = args.state or default_state_file()
    clock = clock or time.time  # a wall clock, so waits carry over between commands

    try:
        contact = args.contact or _contact_from_settings(args.settings)
        options: dict = {
            "clock": clock,
            "wall_clock": lambda: datetime.fromtimestamp(clock(), UTC),
        }
        if transport is not None:
            options["transport"] = transport
        if sleep is not None:
            options["sleep"] = sleep
        fetcher = Fetcher(contact_email=contact, **options)
    except (OSError, ValueError) as error:
        print(f"Stopped: {error}", file=err)
        return EXIT_USAGE

    saved = _read_state(state_path)
    fetcher.carry_over(saved)
    print(f"User-Agent: {fetcher.user_agent}", file=err)
    worst = EXIT_OK
    try:
        for index, url in enumerate(args.urls, start=1):
            worst = max(worst, _fetch_one(fetcher, url, index, args))
    finally:
        _write_state(state_path, {**saved, **fetcher.last_requests()}, clock())
    return worst


def _fetch_one(fetcher: Fetcher, url: str, index: int, args: argparse.Namespace) -> int:
    err = sys.stderr
    try:
        response = fetcher.fetch(url, extra_delay_seconds=args.crawl_delay)
    except DisallowedByRobots as error:
        print(
            f"REFUSED: robots.txt disallows {error.url} for {BOT_NAME}. Nothing was fetched "
            "from that address. Do not fetch it another way; record it on the source's page.",
            file=err,
        )
        return EXIT_DISALLOWED
    except Blocked as error:
        print(
            f"BLOCKED: {error.url}: {error.reason}. Nothing more is asked of this site. "
            "Do not retry or work around it.",
            file=err,
        )
        return EXIT_BLOCKED
    except FetchError as error:
        print(f"FAILED: {error.url}: {error.reason}", file=err)
        return EXIT_FAILED

    check = fetcher.robots_check(response.url)
    if check is not None:
        found = "rules found" if check.status == 200 else "none, so all allowed"
        print(
            f"robots.txt: {check.url} read {check.read_at.isoformat(timespec='seconds')} "
            f"(HTTP {check.status}, {found}); delay {fetcher.delay_seconds(response.url):g} s",
            file=err,
        )
    if args.out_dir:
        target: Path | None = args.out_dir / _file_name(index, response.url)
    else:
        target = args.out
    print(
        f"HTTP {response.status} {response.url}: {len(response.body)} bytes, saved to "
        f"{target or 'standard output'}",
        file=err,
    )
    if target is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.body)
        sidecar = target.with_name(target.name + SIDECAR_SUFFIX)
        sidecar.write_text(
            json.dumps(fetch_record(fetcher, url, response, args.crawl_delay), indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        sys.stdout.buffer.write(response.body)
        sys.stdout.flush()
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
