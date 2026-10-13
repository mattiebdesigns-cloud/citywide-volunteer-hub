"""Event-format checks shared by both repos (PROJECT.md section 4).

The same file lives in `tests/guards/` of both repos; keep them identical.

The schemas belong to pv-schema and live in the public repo:
    docs/event.schema.json        one listing
    docs/events-file.schema.json  the whole events.json file; it refers to
                                  the listing schema by its $id
This module loads both into one registry, so the reference resolves offline.

Dependencies: jsonschema and referencing (both MIT).
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

EVENT_SCHEMA = Path("docs/event.schema.json")
FILE_SCHEMA = Path("docs/events-file.schema.json")


def schemas_present(public_repo: Path) -> bool:
    return (public_repo / EVENT_SCHEMA).is_file() and (public_repo / FILE_SCHEMA).is_file()


def load_schemas(public_repo: Path) -> tuple[dict, dict]:
    event = json.loads((public_repo / EVENT_SCHEMA).read_text(encoding="utf-8"))
    events_file = json.loads((public_repo / FILE_SCHEMA).read_text(encoding="utf-8"))
    return event, events_file


def _format_checker() -> FormatChecker:
    """Format checks without extra packages.

    jsonschema only checks "date-time" and "uri" when optional packages are
    installed, and some of those are not permissively licensed. These two
    small checks use the standard library instead.
    """
    checker = FormatChecker(formats=())

    @checker.checks("date-time", raises=ValueError)
    def _date_time(value: object) -> bool:
        if not isinstance(value, str):
            return True
        parsed = datetime.fromisoformat(value)
        return parsed.tzinfo is not None

    @checker.checks("uri")
    def _uri(value: object) -> bool:
        if not isinstance(value, str):
            return True
        parts = urlparse(value)
        return bool(parts.scheme) and bool(parts.netloc or parts.path)

    return checker


def file_validator(public_repo: Path) -> Draft202012Validator:
    """Validator for a whole events.json file."""
    event, events_file = load_schemas(public_repo)
    registry = Registry().with_resources(
        [
            (event["$id"], Resource.from_contents(event)),
            (events_file["$id"], Resource.from_contents(events_file)),
        ]
    )
    return Draft202012Validator(events_file, registry=registry, format_checker=_format_checker())


def event_validator(public_repo: Path) -> Draft202012Validator:
    """Validator for one listing."""
    event, _ = load_schemas(public_repo)
    return Draft202012Validator(event, format_checker=_format_checker())


def schema_errors(validator: Draft202012Validator, data: object) -> list[str]:
    """Readable list of everything wrong, with where it is."""
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(top)'}: {e.message}" for e in errors]


def duplicate_ids(data: dict) -> list[str]:
    """Listing ids that appear more than once (JSON Schema cannot check this)."""
    counts = Counter(e.get("id") for e in data.get("events", []) if isinstance(e, dict))
    return sorted(str(i) for i, n in counts.items() if n > 1)
