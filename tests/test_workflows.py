"""CI workflow safety (PROJECT.md section 13; security checklist).

Identical in both repos.

- Every action is pinned to a full commit id, so a moved tag cannot change what runs.
- No workflow uses pull_request_target, which would run code from a fork with
  this repo's permissions.
- Every workflow states its permissions, and none grants write access.
- No workflow reads a secret. (When the nightly deploy needs one, that
  workflow gets its own reviewed exception here, with the security gatekeeper.)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.y*ml"))

USES = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
PINNED = re.compile(r"^[\w.\-]+/[\w.\-/]+@[0-9a-f]{40}$")


def _code(path: Path) -> str:
    """Workflow text without comments, so a comment cannot trip or hide a check."""
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        lines.append(re.sub(r"(^|\s)#.*$", "", line))
    return "\n".join(lines)


def test_there_are_workflows():
    assert WORKFLOWS, "no workflow files in .github/workflows/"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_actions_are_pinned_to_a_commit(path: Path):
    loose = [
        u
        for u in USES.findall(_code(path))
        if not u.startswith(("./", "docker://")) and not PINNED.match(u)
    ]
    assert not loose, f"actions not pinned to a full commit id: {loose}"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_no_pull_request_target(path: Path):
    assert "pull_request_target" not in _code(path)


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_permissions_are_declared(path: Path):
    assert re.search(r"^permissions:", _code(path), re.MULTILINE)


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_no_write_permission(path: Path):
    code = _code(path)
    assert not re.search(r":\s*write\b", code), "a workflow grants write access"
    assert "write-all" not in code, "a workflow grants write access"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_no_secrets_used(path: Path):
    assert not re.search(r"\bsecrets\.", _code(path)), "a workflow reads a secret"
