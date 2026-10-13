"""Licence check for Python packages (PROJECT.md section 3, rule 8).

The same file lives in `tests/guards/` of both repos; keep them identical.

Allowed licences: MIT, Apache-2.0, BSD, ISC, PSF-2.0 (PSF-2.0 by the owner's
decision 0003). Anything else fails, including a
package whose licence cannot be read. The fix for a failure is never to edit
this file on your own: remove the package, or ask the coordinator, who routes
it to the scraping and licence gatekeeper.

Two checks:

1. Installed packages: every package in the environment the tests run in.
2. Locked packages: every package in uv.lock, for every platform and Python
   version, including ones the current machine did not install. Their licence
   is read from the Python Package Index (pypi.org), so this check needs the
   network.

How a package is judged:

- If it states a licence expression (SPDX, for example "MIT OR Apache-2.0"),
  that expression alone decides. AND means every part must be allowed; OR
  means at least one part must be; "X WITH exception" is judged by X.
- Otherwise its licence classifiers decide: every one must be allowed, and
  none may name a blocked licence. With no classifiers, its free-text licence
  field decides the same way.

Command line:
    python tests/guards/licence_check.py             # installed packages
    python tests/guards/licence_check.py uv.lock     # also every locked package
Exit code 0 means every package is allowed, 1 means at least one is not.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
import urllib.error
import urllib.request
from importlib import metadata
from pathlib import Path

# SPDX ids that are allowed. Matched against the whole id.
ALLOWED_IDS = re.compile(
    r"^(MIT|MIT-0|Apache-2\.0|ISC|0BSD|BSD-[1-4]-Clause(-[A-Za-z]+)?|PSF-2\.0)$", re.IGNORECASE
)

# For packages without an expression: words in a classifier or licence field.
ALLOWED_WORDS = ("MIT", "Apache", "BSD", "ISC", "PSF", "Python Software Foundation")
BLOCKED_WORDS = ("GPL", "AGPL", "LGPL", "SSPL", "BUSL", "Business Source", "Commons Clause",
                 "Elastic License", "source-available", "Source Available")

# Packages reviewed by the scraping and licence gatekeeper whose metadata is
# missing or unclear, mapped to the licence the gatekeeper confirmed.
# Add an entry only with the gatekeeper's written approval.
REVIEWED: dict[str, str] = {}

# Tools that sit in every environment and are not part of the project.
IGNORED = {"pip", "setuptools", "wheel"}

PYPI_JSON = "https://pypi.org/pypi/{name}/{version}/json"


class NetworkUnavailable(Exception):
    """pypi.org could not be reached, so locked packages could not be checked."""


# ---------------------------------------------------------------------------
# Judging one package
# ---------------------------------------------------------------------------


class _ExpressionError(ValueError):
    pass


def expression_allowed(expression: str) -> bool:
    """True if an SPDX licence expression is allowed. Unreadable means no."""
    tokens = re.findall(r"\(|\)|[^\s()]+", expression)
    position = 0

    def peek() -> str | None:
        return tokens[position] if position < len(tokens) else None

    def take() -> str:
        nonlocal position
        if position >= len(tokens):
            raise _ExpressionError("expression ends too early")
        position += 1
        return tokens[position - 1]

    def parse_or() -> bool:
        result = parse_and()
        while (peek() or "").upper() == "OR":
            take()
            right = parse_and()
            result = result or right
        return result

    def parse_and() -> bool:
        result = parse_atom()
        while (peek() or "").upper() == "AND":
            take()
            right = parse_atom()
            result = result and right
        return result

    def parse_atom() -> bool:
        token = take()
        if token == "(":
            result = parse_or()
            if take() != ")":
                raise _ExpressionError("missing )")
            return result
        if token == ")" or token.upper() in {"AND", "OR", "WITH"}:
            raise _ExpressionError(f"unexpected {token}")
        if (peek() or "").upper() == "WITH":
            take()
            take()  # the exception only adds permissions; the base licence decides
        return bool(ALLOWED_IDS.match(token.rstrip("+")))

    try:
        result = parse_or()
        if position != len(tokens):
            raise _ExpressionError("text left over")
        return result
    except _ExpressionError:
        return False


def _words_allowed(text: str) -> bool:
    if any(re.search(rf"\b{re.escape(w)}", text, re.IGNORECASE) for w in BLOCKED_WORDS):
        return False
    return any(re.search(rf"\b{w}", text, re.IGNORECASE) for w in ALLOWED_WORDS)


def judge(expression: str | None, classifiers: list[str], licence_field: str | None) -> str | None:
    """None if the package is allowed, otherwise the reason it is not."""
    if expression and expression.strip():
        expression = expression.strip()
        if expression_allowed(expression):
            return None
        return f"licence expression not allowed ({expression})"
    licences = [
        c.split("::")[-1].strip()
        for c in classifiers
        if c.startswith("License ::") and c.strip() != "License :: OSI Approved"
    ]
    if licences:
        bad = [text for text in licences if not _words_allowed(text)]
        return f"licence not allowed ({'; '.join(bad)})" if bad else None
    text = (licence_field or "").strip()
    if not text or text.upper() == "UNKNOWN":
        return "no licence information"
    first_line = text.splitlines()[0]  # some packages paste the whole licence text
    return None if _words_allowed(first_line) else f"licence not allowed ({first_line[:80]})"


def _key(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


# ---------------------------------------------------------------------------
# 1. Installed packages
# ---------------------------------------------------------------------------


def check_installed() -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for dist in metadata.distributions():
        name = (dist.metadata.get("Name") or "").strip()
        key = _key(name)
        if not name or key in seen or key in IGNORED or key in REVIEWED:
            continue
        seen.add(key)
        meta = dist.metadata
        reason = judge(
            meta.get("License-Expression"), meta.get_all("Classifier") or [], meta.get("License")
        )
        if reason:
            problems.append(f"{name} {dist.version} (installed): {reason}")
    return sorted(problems)


# ---------------------------------------------------------------------------
# 2. Locked packages
# ---------------------------------------------------------------------------


def locked_packages(lock_file: Path) -> list[dict]:
    with lock_file.open("rb") as handle:
        return tomllib.load(handle).get("package", [])


def _pypi_info(name: str, version: str) -> dict:
    url = PYPI_JSON.format(name=name, version=version)
    try:
        with urllib.request.urlopen(url, timeout=20) as response:  # fixed https URL to pypi.org
            return json.load(response)["info"]
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {}
        raise NetworkUnavailable(f"{url}: HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise NetworkUnavailable(str(error)) from error


def check_lock(lock_file: Path) -> list[str]:
    """Every package in uv.lock. Raises NetworkUnavailable if pypi.org cannot be reached."""
    problems: list[str] = []
    for package in locked_packages(lock_file):
        name, version = package.get("name", "?"), package.get("version", "?")
        source = package.get("source", {})
        key = _key(name)
        if "virtual" in source or "editable" in source:
            continue  # the project itself
        if key in IGNORED or key in REVIEWED:
            continue
        if "pypi.org" not in str(source.get("registry", "")):
            problems.append(f"{name} {version} (uv.lock): not from pypi.org, check its licence by hand")
            continue
        info = _pypi_info(name, version)
        if not info:
            problems.append(f"{name} {version} (uv.lock): not found on pypi.org")
            continue
        reason = judge(info.get("license_expression"), info.get("classifiers") or [],
                       info.get("license"))
        if reason:
            problems.append(f"{name} {version} (uv.lock): {reason}")
    return sorted(problems)


def check() -> list[str]:
    """Installed packages only (kept for callers that do not have a lock file)."""
    return check_installed()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    problems = check_installed()
    if args:
        try:
            problems += check_lock(Path(args[0]))
        except NetworkUnavailable as error:
            print(f"Could not reach pypi.org to check {args[0]}: {error}")
            return 1
    if problems:
        print("Packages without an allowed licence (MIT, Apache-2.0, BSD, ISC, PSF-2.0):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Every package has an allowed licence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
