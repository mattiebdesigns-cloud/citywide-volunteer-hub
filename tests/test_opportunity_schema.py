"""Flexible opportunity format checks (PROJECT.md sections 2, 4, 5; decision 0018).

Schemas by pv-schema in docs/:
    docs/opportunity.schema.json          one program with no set times
    docs/opportunities-file.schema.json   the whole opportunities.json file

The opportunity schema points at the event schema for every shared field, so
all three schemas load into one registry and resolve offline.

- All three schema files are valid JSON Schema (draft 2020-12).
- Every opportunities.json sample validates and has unique ids.
- The shared fields are exactly the event fields decision 0018 names, plus
  commitment: no dates, no schedule, no open-spots counts.
- The schema rejects what it must reject, so a loosened schema is caught.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from guards import event_schema

ROOT = Path(__file__).resolve().parent.parent
OPPORTUNITY = ROOT / "docs/opportunity.schema.json"
FILE = ROOT / "docs/opportunities-file.schema.json"
SAMPLE = ROOT / "docs/examples/opportunities.sample.json"

# Decision 0018, point 3: the listing fields that do not need a date, plus commitment.
DECISION_0018_FIELDS = [
    "id", "org_name", "title", "address", "area", "section", "neighborhood_or_town", "cause",
    "type", "sensitive", "photos_allowed", "signup_url", "join_method", "min_age",
    "listing_language", "spanish_spoken", "training_required", "clearances_required",
    "group_friendly", "source_url", "source_id", "last_seen_at", "host_type", "faith_tradition",
    "activity", "commitment",
]  # fmt: skip


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    event, _ = event_schema.load_schemas(ROOT)
    opportunity, file_schema = _load(OPPORTUNITY), _load(FILE)
    registry = Registry().with_resources(
        [(s["$id"], Resource.from_contents(s)) for s in (event, opportunity, file_schema)]
    )
    return Draft202012Validator(
        file_schema, registry=registry, format_checker=event_schema._format_checker()
    )


def _errors(data: object) -> list[str]:
    return event_schema.schema_errors(_validator(), data)


def opportunities_files() -> list[Path]:
    found = list((ROOT / "docs/examples").glob("opportunities*.json"))
    found += list((ROOT / "tests/fixtures/opportunities").glob("*.json"))
    site = ROOT / "site"
    if site.is_dir():
        found += [
            p
            for p in site.rglob("opportunities*.json")
            if "node_modules" not in p.parts and "dist" not in p.parts
        ]
    return sorted(found)


def test_schemas_are_valid_json_schema():
    Draft202012Validator.check_schema(_load(OPPORTUNITY))
    Draft202012Validator.check_schema(_load(FILE))


def test_fields_are_the_ones_decision_0018_names():
    schema = _load(OPPORTUNITY)
    assert sorted(schema["properties"]) == sorted(DECISION_0018_FIELDS)
    assert sorted(schema["required"]) == sorted(DECISION_0018_FIELDS)


def test_shared_fields_point_at_the_event_schema():
    event, _ = event_schema.load_schemas(ROOT)
    schema = _load(OPPORTUNITY)
    for name, prop in schema["properties"].items():
        if name == "commitment":
            continue
        assert name in event["properties"], f"{name} is not an event field"
        assert prop.get("$ref") == f"{event['$id']}#/properties/{name}", name


@pytest.mark.parametrize("path", opportunities_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_opportunities_file_matches_schema(path: Path):
    errors = _errors(_load(path))
    assert not errors, "\n".join(errors)


@pytest.mark.parametrize("path", opportunities_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_opportunity_ids_are_unique(path: Path):
    counts = Counter(o.get("id") for o in _load(path)["opportunities"])
    assert not [i for i, n in counts.items() if n > 1]


def test_sample_uses_invented_organizations_only():
    for item in _load(SAMPLE)["opportunities"]:
        for key in ("signup_url", "source_url"):
            assert ".example.org/" in item[key], f"{item['id']} {key} is not an example.org link"


# Each case changes one field of a valid program; the schema must reject it.
BAD = {
    "missing id": lambda o: o.pop("id"),
    "missing commitment": lambda o: o.pop("commitment"),
    "missing source_id": lambda o: o.pop("source_id"),
    "empty source_id": lambda o: o.update(source_id=""),
    "commitment as an empty string": lambda o: o.update(commitment=""),
    "commitment as a number of hours": lambda o: o.update(commitment=2),
    "a start time": lambda o: o.update(start="2026-11-10T10:00:00-05:00"),
    "an end time": lambda o: o.update(end="2026-11-10T12:00:00-05:00"),
    "recurring": lambda o: o.update(recurring=True),
    "a schedule": lambda o: o.update(recurrence_rule="FREQ=WEEKLY;BYDAY=SA"),
    "open-spots count": lambda o: o.update(spots_left=3),
    "unknown field (no attendee or sign-up lists)": lambda o: o.update(attendees=["A. Person"]),
    "type not in the list": lambda o: o.update(type="party"),
    "join_method as free text": lambda o: o.update(join_method="call us"),
    "spanish_spoken null instead of unknown": lambda o: o.update(spanish_spoken=None),
    "signup_url not a web link": lambda o: o.update(signup_url="mailto:someone@example.org"),
    "last_seen_at without a UTC offset": lambda o: o.update(last_seen_at="2026-11-02T00:00:00"),
    "section typed as a place name": lambda o: o.update(section="River Wards"),
    "protest_action not marked sensitive": lambda o: o.update(
        type="protest_action", sensitive=False
    ),
}

# Each case changes a valid program in a way the schema must still accept.
GOOD = {
    "commitment null": lambda o: o.update(commitment=None),
    "sensitive program": lambda o: o.update(sensitive=True),
    "protest_action marked sensitive": lambda o: o.update(type="protest_action", sensitive=True),
    "no address, section or neighborhood": lambda o: o.update(
        address=None, section=None, neighborhood_or_town=None
    ),
}


def _sample_with(edit) -> dict:
    data = _load(SAMPLE)
    edit(data["opportunities"][0])
    return data


@pytest.mark.parametrize("case", sorted(BAD))
def test_schema_rejects_bad_opportunity(case: str):
    assert _errors(_sample_with(BAD[case])), f"schema accepted a program with: {case}"


@pytest.mark.parametrize("case", sorted(GOOD))
def test_schema_accepts_good_opportunity(case: str):
    errors = _errors(_sample_with(GOOD[case]))
    assert not errors, f"schema rejected a valid program ({case}):\n" + "\n".join(errors)


def test_file_needs_generated_at_and_opportunities():
    for key in ("generated_at", "opportunities"):
        data = copy.deepcopy(_load(SAMPLE))
        data.pop(key)
        assert _errors(data), f"file without {key} accepted"


def test_events_file_is_not_an_opportunities_file():
    # The two files stay apart (decision 0018, point 2).
    assert _errors(_load(ROOT / "docs/examples/events.sample.json"))
