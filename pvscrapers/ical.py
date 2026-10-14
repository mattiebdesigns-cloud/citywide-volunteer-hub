"""A small iCalendar (RFC 5545) reader: enough to read event feeds.

Standard library only. It reads the structure (calendars, events, their
properties) and turns dates and text into Python values. It does not expand
repeat rules; a scraper passes an RRULE through as text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ICalError(ValueError):
    """The text is not a readable iCalendar file."""


@dataclass
class Property:
    name: str  # upper case
    params: dict[str, str]  # names upper case, values unquoted
    value: str  # raw, still escaped


@dataclass
class Component:
    name: str  # upper case, e.g. VCALENDAR, VEVENT
    properties: list[Property] = field(default_factory=list)
    children: list[Component] = field(default_factory=list)

    def first(self, name: str) -> Property | None:
        name = name.upper()
        return next((p for p in self.properties if p.name == name), None)

    def all(self, name: str) -> list[Property]:
        name = name.upper()
        return [p for p in self.properties if p.name == name]

    def text(self, name: str) -> str | None:
        prop = self.first(name)
        if prop is None:
            return None
        value = unescape(prop.value).strip()
        return value or None

    def walk(self, name: str) -> list[Component]:
        name = name.upper()
        found = [self] if self.name == name else []
        for child in self.children:
            found += child.walk(name)
        return found


def unfold(text: str) -> list[str]:
    """Join folded lines (a line break followed by one space or tab)."""
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    return [line for line in re.sub(r"\n[ \t]", "", text).split("\n") if line.strip()]


def _split_content_line(line: str) -> Property:
    """NAME;PARAM=a;PARAM2="b:c":VALUE -> Property. Quoted values may hold ; and :."""
    params: dict[str, str] = {}
    i, n = 0, len(line)
    while i < n and line[i] not in ";:":
        i += 1
    name = line[:i].strip().upper()
    if not name or i >= n:
        raise ICalError(f"not a content line: {line[:40]!r}")
    while i < n and line[i] == ";":
        i += 1
        start = i
        while i < n and line[i] != "=":
            i += 1
        key = line[start:i].strip().upper()
        i += 1
        values: list[str] = []
        while True:
            if i < n and line[i] == '"':
                end = line.find('"', i + 1)
                if end == -1:
                    raise ICalError(f"unclosed quote in: {line[:40]!r}")
                values.append(line[i + 1 : end])
                i = end + 1
            else:
                start = i
                while i < n and line[i] not in ",;:":
                    i += 1
                values.append(line[start:i])
            if i < n and line[i] == ",":
                i += 1
                continue
            break
        params[key] = ",".join(values)
    if i >= n or line[i] != ":":
        raise ICalError(f"no value in: {line[:40]!r}")
    return Property(name=name, params=params, value=line[i + 1 :])


def parse(text: str) -> Component:
    """Read an iCalendar file and return its first VCALENDAR."""
    root = Component("ROOT")
    stack = [root]
    for line in unfold(text):
        prop = _split_content_line(line)
        if prop.name == "BEGIN":
            child = Component(prop.value.strip().upper())
            stack[-1].children.append(child)
            stack.append(child)
        elif prop.name == "END":
            if len(stack) == 1 or stack[-1].name != prop.value.strip().upper():
                raise ICalError(f"END:{prop.value} does not close an open BEGIN")
            stack.pop()
        else:
            stack[-1].properties.append(prop)
    if len(stack) != 1:
        raise ICalError(f"BEGIN:{stack[-1].name} is never closed")
    calendars = root.walk("VCALENDAR")
    if not calendars:
        raise ICalError("no VCALENDAR in the file")
    return calendars[0]


def unescape(value: str) -> str:
    """Undo iCalendar text escapes: \\n, \\N, \\, \\; and \\\\."""
    return re.sub(r"\\([nN,;\\])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), value)


def split_list(value: str) -> list[str]:
    """Split an escaped comma list (CATEGORIES) into its items."""
    items, current, i = [], [], 0
    while i < len(value):
        char = value[i]
        if char == "\\" and i + 1 < len(value):
            current.append(value[i : i + 2])
            i += 2
            continue
        if char == ",":
            items.append("".join(current))
            current = []
        else:
            current.append(char)
        i += 1
    items.append("".join(current))
    return [unescape(item).strip() for item in items if unescape(item).strip()]


def zone(name: str | None) -> ZoneInfo | None:
    """An IANA time zone by name, or None if the name is not one."""
    if not name:
        return None
    try:
        return ZoneInfo(name.strip())
    except (ZoneInfoNotFoundError, ValueError):
        return None


@dataclass(frozen=True)
class When:
    """A DTSTART or DTEND value."""

    value: datetime | date
    all_day: bool  # a DATE, with no time of day
    floating: bool  # a time with no zone at all


def read_when(prop: Property, fallback_zone: ZoneInfo | None) -> When:
    """Turn a DTSTART/DTEND property into a When.

    A time with TZID uses that zone; a time ending in Z is UTC; a time with
    neither is "floating" and takes `fallback_zone` if one is given.
    Raises ICalError for an unreadable value or an unknown TZID.
    """
    raw = prop.value.strip()
    if prop.params.get("VALUE", "").upper() == "DATE" or re.fullmatch(r"\d{8}", raw):
        try:
            return When(datetime.strptime(raw, "%Y%m%d").date(), all_day=True, floating=False)
        except ValueError as error:
            raise ICalError(f"unreadable date {raw!r}") from error
    match = re.fullmatch(r"(\d{8}T\d{6})(Z?)", raw)
    if not match:
        raise ICalError(f"unreadable date-time {raw!r}")
    try:
        moment = datetime.strptime(match.group(1), "%Y%m%dT%H%M%S")
    except ValueError as error:
        raise ICalError(f"unreadable date-time {raw!r}") from error
    if match.group(2):
        return When(moment.replace(tzinfo=UTC), all_day=False, floating=False)
    tzid = prop.params.get("TZID")
    if tzid:
        tz = zone(tzid)
        if tz is None:
            raise ICalError(f"unknown time zone {tzid!r}")
        return When(moment.replace(tzinfo=tz), all_day=False, floating=False)
    if fallback_zone is not None:
        return When(moment.replace(tzinfo=fallback_zone), all_day=False, floating=False)
    return When(moment, all_day=False, floating=True)
