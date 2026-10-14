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
  429) it stops and raises `Blocked`. It never retries, and never tries
  another way in. A robots.txt that cannot be read (server error, network
  failure) also stops the source, as RFC 9309 asks.
- No retries at all: a failed fetch is reported, and the next nightly run tries again.
"""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import Message
from urllib.parse import urljoin, urlsplit

from pvscrapers import __version__
from pvscrapers.robots import RobotsRules

BOT_NAME = "CitywideVolunteerHubBot"
FLOOR_DELAY_SECONDS = 1.0  # never wait less than this between requests to one site
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
    _robots: dict[str, RobotsRules] = field(default_factory=dict, init=False, repr=False)
    _last_request: dict[str, float] = field(default_factory=dict, init=False, repr=False)
    _user_agent: str = field(default="", init=False, repr=False)

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
        if _cloudflare_challenge(response):
            raise Blocked(response.url, "Cloudflare challenge; our bot is not let in")
        if response.status in (401, 403):
            raise Blocked(response.url, f"HTTP {response.status}; our bot is not let in")
        if response.status == 429:
            raise Blocked(response.url, "HTTP 429; the site asks us to slow down")

    def _gap(self, origin: str, extra_delay: float) -> float:
        rules = self._robots.get(origin)
        site_delay = rules.crawl_delay if rules and rules.crawl_delay else 0.0
        return max(FLOOR_DELAY_SECONDS, self.min_delay_seconds, site_delay, extra_delay)

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
