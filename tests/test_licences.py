"""Every Python package has an allowed licence (PROJECT.md section 3, rule 8;
PSF-2.0 allowed by decision 0003).

Identical in both repos. The lock-file check reads licences from pypi.org.
Offline on a laptop it skips; in CI (where GitHub sets CI=true) it fails
instead, so CI can never pass without checking.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from guards import licence_check

ROOT = Path(__file__).resolve().parent.parent
LOCK_FILE = ROOT / "uv.lock"


def test_installed_packages_are_permissive():
    problems = licence_check.check_installed()
    assert not problems, "\n".join(problems)


def test_locked_packages_are_permissive():
    """Every package in uv.lock, for every platform and Python version."""
    assert LOCK_FILE.is_file(), "uv.lock is missing; run `uv lock`"
    try:
        problems = licence_check.check_lock(LOCK_FILE)
    except licence_check.NetworkUnavailable as error:
        if os.environ.get("CI") == "true":
            pytest.fail(f"could not reach pypi.org to check uv.lock: {error}")
        pytest.skip(f"offline, uv.lock not checked: {error}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize(
    ("expression", "allowed"),
    [
        ("MIT", True),
        ("Apache-2.0", True),
        ("BSD-3-Clause", True),
        ("ISC", True),
        ("MIT OR Apache-2.0", True),
        ("(MIT OR Apache-2.0) AND BSD-3-Clause", True),
        ("Apache-2.0 WITH LLVM-exception", True),
        ("MIT AND MPL-2.0", False),
        ("MPL-2.0", False),
        ("PSF-2.0", True),
        ("PSF-2.0 AND GPL-3.0", False),
        ("PSF-2.0 OR GPL-3.0-only", True),
        ("GPL-3.0-only", False),
        ("MIT AND (GPL-2.0-only OR MPL-2.0)", False),
        ("GPL-2.0-only WITH Classpath-exception-2.0", False),
        ("LicenseRef-Proprietary", False),
        ("MIT AND", False),
        ("(MIT", False),
    ],
)
def test_licence_expression_rules(expression: str, allowed: bool):
    assert licence_check.expression_allowed(expression) is allowed


def test_expression_alone_decides_when_present():
    # A permissive classifier must not rescue a disallowed expression.
    classifiers = ["License :: OSI Approved :: MIT License"]
    assert licence_check.judge("MIT AND MPL-2.0", classifiers, "MIT")


def test_without_expression_every_classifier_must_be_allowed():
    classifiers = [
        "License :: OSI Approved :: MIT License",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
    ]
    assert licence_check.judge(None, classifiers, None)
    assert licence_check.judge(None, classifiers[:1], None) is None


def test_missing_licence_fails():
    assert licence_check.judge(None, [], None)
    assert licence_check.judge(None, [], "UNKNOWN")
