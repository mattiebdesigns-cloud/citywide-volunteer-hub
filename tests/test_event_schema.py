"""Event format checks (PROJECT.md section 4; schema by pv-schema in docs/).

- Both schema files are valid JSON Schema (draft 2020-12).
- Every events.json in this repo validates: the sample in docs/examples/,
  any sample the site ships, and any fixture in tests/fixtures/events/.
- Listing ids in each file are unique (JSON Schema cannot check this).
- The schema rejects listings it must reject, so a loosened schema is caught.

Skips cleanly while the schema files do not exist yet.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from guards import event_schema

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    not event_schema.schemas_present(ROOT),
    reason="event schema not in docs/ yet (pv-schema, task 0.1)",
)


def events_files() -> list[Path]:
    found = list((ROOT / "docs/examples").glob("*.json"))
    found += list((ROOT / "tests/fixtures/events").glob("*.json"))
    site = ROOT / "site"
    if site.is_dir():
        found += [
            p for p in site.rglob("events*.json")
            if "node_modules" not in p.parts and "dist" not in p.parts
        ]
    return sorted(found)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sample() -> dict:
    return _load(ROOT / "docs/examples/events.sample.json")


def test_schemas_are_valid_json_schema():
    event, events_file = event_schema.load_schemas(ROOT)
    Draft202012Validator.check_schema(event)
    Draft202012Validator.check_schema(events_file)


def test_there_is_at_least_one_sample_to_check():
    assert events_files(), "no events.json sample found to validate"


@pytest.mark.parametrize("path", events_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_events_file_matches_schema(path: Path):
    errors = event_schema.schema_errors(event_schema.file_validator(ROOT), _load(path))
    assert not errors, "\n".join(errors)


@pytest.mark.parametrize("path", events_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_listing_ids_are_unique(path: Path):
    dupes = event_schema.duplicate_ids(_load(path))
    assert not dupes, f"listing ids used more than once: {dupes}"


def test_duplicate_id_check_catches_a_duplicate():
    data = _sample()
    data["events"].append(copy.deepcopy(data["events"][0]))
    assert event_schema.duplicate_ids(data) == [data["events"][0]["id"]]


# Each case changes one field of a valid listing; the schema must reject it.
BAD_LISTINGS = {
    "missing id": lambda e: e.pop("id"),
    "unknown field (no attendee or sign-up lists)": lambda e: e.update(attendees=["A. Person"]),
    "type not in the list": lambda e: e.update(type="party"),
    "join_method guessed as free text": lambda e: e.update(join_method="maybe"),
    "start without a UTC offset": lambda e: e.update(start="2026-11-01T09:00:00"),
    "start not a real date": lambda e: e.update(start="2026-13-45T09:00:00-05:00"),
    "signup_url not a web link": lambda e: e.update(signup_url="mailto:someone@example.org"),
    "spanish_spoken null instead of unknown": lambda e: e.update(spanish_spoken=None),
    "protest_action not marked sensitive": lambda e: e.update(type="protest_action", sensitive=False),
    "schedule on a one-off listing": lambda e: e.update(
        recurring=False, recurrence_rule="FREQ=WEEKLY;BYDAY=TU"
    ),
    # Open spots (decision 0008; PROJECT.md 4).
    "full listing with spots left": lambda e: e.update(spots_left=2, spots_total=10, full=True),
    "negative spots_left": lambda e: e.update(spots_left=-1, spots_total=10, full=False),
    "spots_total of 0": lambda e: e.update(spots_left=0, spots_total=0, full=False),
}

# Each case changes a valid listing in a way the schema must still accept.
GOOD_LISTINGS = {
    # The owner allows counts on sensitive listings (decision 0008 as amended).
    "sensitive listing with spots_left": lambda e: e.update(
        sensitive=True, spots_left=3, spots_total=None, full=False
    ),
    "sensitive listing with spots_total": lambda e: e.update(
        sensitive=True, spots_left=None, spots_total=20, full=False
    ),
    "sensitive listing marked full, no counts": lambda e: e.update(
        sensitive=True, spots_left=None, spots_total=None, full=True
    ),
    "sensitive listing with the open-spots fields left out": lambda e: (
        e.update(sensitive=True),
        e.pop("spots_left", None),
        e.pop("spots_total", None),
        e.pop("full", None),
    ),
    "ordinary listing with counts": lambda e: e.update(
        sensitive=False, spots_left=3, spots_total=10, full=False
    ),
    "ordinary listing full with 0 left": lambda e: e.update(
        sensitive=False, spots_left=0, spots_total=10, full=True
    ),
}


@pytest.mark.parametrize("case", sorted(BAD_LISTINGS))
def test_schema_rejects_bad_listing(case: str):
    data = _sample()
    BAD_LISTINGS[case](data["events"][0])
    errors = event_schema.schema_errors(event_schema.file_validator(ROOT), data)
    assert errors, f"schema accepted a listing with: {case}"


@pytest.mark.parametrize("case", sorted(GOOD_LISTINGS))
def test_schema_accepts_good_listing(case: str):
    data = _sample()
    GOOD_LISTINGS[case](data["events"][0])
    errors = event_schema.schema_errors(event_schema.file_validator(ROOT), data)
    assert not errors, f"schema rejected a valid listing ({case}):\n" + "\n".join(errors)


def test_file_without_generated_at_is_rejected():
    data = _sample()
    data.pop("generated_at")
    assert event_schema.schema_errors(event_schema.file_validator(ROOT), data)
