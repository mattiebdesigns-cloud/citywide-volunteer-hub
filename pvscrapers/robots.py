"""A small robots.txt reader that follows RFC 9309.

Python's own `urllib.robotparser` treats `*` and `$` in a rule as plain
characters, so a rule like `Disallow: */feed/*` would never match. This
reader handles them:

- Groups are chosen by our bot's product token (case-insensitive). Every
  group naming it applies; if none does, the `*` groups apply; if there are
  none, everything is allowed.
- The longest matching rule wins. On a tie between Allow and Disallow,
  Allow wins. `*` matches any run of characters, `$` anchors the end.
- `Crawl-delay` is not in the RFC but many sites use it; we obey the
  largest value in the groups that apply to us. A Crawl-delay written before
  any User-agent line (some sites put it on the first line) applies to every
  bot, so it counts too. A Crawl-delay we cannot read (for example "10s")
  is kept as `unreadable_crawl_delay`; the fetcher then stops that site
  rather than guess how long to wait.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass
class _Group:
    agents: list[str] = field(default_factory=list)
    rules: list[tuple[bool, str]] = field(default_factory=list)  # (allow, pattern)
    crawl_delay: float | None = None
    unreadable_delay: str | None = None


def _pattern_regex(pattern: str) -> re.Pattern[str]:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = ".*".join(re.escape(part) for part in body.split("*"))
    return re.compile(regex + ("$" if anchored else ""))


@dataclass
class RobotsRules:
    """The rules from one robots.txt that apply to one bot."""

    rules: list[tuple[bool, str]] = field(default_factory=list)
    crawl_delay: float | None = None
    unreadable_crawl_delay: str | None = None
    allow_all: bool = False
    disallow_all: bool = False

    @classmethod
    def allowing_everything(cls) -> RobotsRules:
        return cls(allow_all=True)

    @classmethod
    def blocking_everything(cls) -> RobotsRules:
        return cls(disallow_all=True)

    @classmethod
    def parse(cls, text: str, product_token: str) -> RobotsRules:
        groups: list[_Group] = []
        current: _Group | None = None
        site_wide_delay: float | None = None
        site_wide_unreadable: str | None = None
        last_was_agent = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if current is None or not last_was_agent:
                    current = _Group()
                    groups.append(current)
                current.agents.append(value.split("/", 1)[0].strip().lower())
                last_was_agent = True
                continue
            last_was_agent = False
            if key == "crawl-delay":
                try:
                    delay = float(value)
                except ValueError:
                    delay = -1.0
                if not delay >= 0 or delay == float("inf"):  # also catches nan
                    if current is None:
                        site_wide_unreadable = value
                    else:
                        current.unreadable_delay = value
                    continue
                if current is None:
                    site_wide_delay = max(site_wide_delay or 0.0, delay)
                else:
                    current.crawl_delay = max(current.crawl_delay or 0.0, delay)
            elif current is None:
                continue  # Allow/Disallow before any user-agent line belong to no group
            elif key in ("allow", "disallow") and value:
                current.rules.append((key == "allow", value))

        token = product_token.lower()
        mine = [g for g in groups if token in g.agents]
        if not mine:
            mine = [g for g in groups if "*" in g.agents]
        delays = [g.crawl_delay for g in mine if g.crawl_delay is not None]
        if site_wide_delay is not None:
            delays.append(site_wide_delay)
        unreadable = [g.unreadable_delay for g in mine if g.unreadable_delay is not None]
        if site_wide_unreadable is not None:
            unreadable.append(site_wide_unreadable)
        return cls(
            rules=[rule for g in mine for rule in g.rules],
            crawl_delay=max(delays) if delays else None,
            unreadable_crawl_delay=unreadable[0] if unreadable else None,
        )

    def allowed(self, url: str) -> bool:
        if self.disallow_all:
            return False
        if self.allow_all:
            return True
        parts = urlsplit(url)
        target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        best_length = -1
        best_allow = True
        for allow, pattern in self.rules:
            if not _pattern_regex(pattern).match(target):
                continue
            length = len(pattern)
            if length > best_length or (length == best_length and allow):
                best_length, best_allow = length, allow
        return best_allow
