"""Repository guards shared by both repos (PROJECT.md sections 3 and 13).

Standard library only, so it adds no dependency. The same file lives in
`tests/guards/` of the private repo and of the public repo; keep them identical.

Two checks:

1. Public-repo leak check. Every path in the public repo, now and anywhere
   in its history, must be on the public repo's allow list (its CLAUDE.md
   "What belongs here"). As a second layer, a block list names the private
   folders (config/, supabase/, support/, outreach/, web/ and more), private
   source lists and .env files, wherever they turn up. When the private repo
   is available it also compares contents: no file of the private repo may
   have an exact copy anywhere in the public repo's history, except the few
   test files the two repos share on purpose.

2. Secret scan. Looks for key-shaped text, and for passwords written into
   web addresses (scheme://user:password@host), in tracked files and in every
   added line of the git history, and in every commit and tag message. It never
   prints the matched text, only the
   file, line and kind of key. A line that is a known false positive can carry
   the marker `pv-secret-scan: allow`; the security gatekeeper reviews every
   use of that marker.

Command line:
    python tests/guards/repo_guard.py leaks <public-repo> [--private <private-repo>]
    python tests/guards/repo_guard.py secrets <repo>
Exit code 0 means clean, 1 means a finding.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# ---------------------------------------------------------------------------
# 1. Public-repo leak check
# ---------------------------------------------------------------------------

# Layer 1: the allow list. What may be in the public repo at all
# (public repo CLAUDE.md, "What belongs here"; PROJECT.md 3).
PUBLIC_ALLOWED_FOLDERS = ("pvscrapers/", "site/", "tests/", ".github/", "docs/examples/")
PUBLIC_ALLOWED_FILES = {
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "CLAUDE.md",
    "pyproject.toml",
    "uv.lock",
    ".gitignore",
    "docs/EVENT-FORMAT.md",
    "docs/design.md",  # pv-design's guide to the site's look; no city or private data
}
PUBLIC_ALLOWED_PATTERNS = (re.compile(r"^docs/[^/]+\.schema\.json$"),)

# Layer 2: the block list, checked first, so it wins inside allowed folders.
# Folders that exist only in the private repo (PROJECT.md 3 and 13, rule 7).
PRIVATE_TOP_FOLDERS = ("config", "supabase", "support", "outreach", "web")
# Private paths below the top level. docs/sources/ is the per-source research,
# which together is a source list. Campaign fixtures stay private (PROJECT.md 8).
PRIVATE_SUB_FOLDERS = (
    "docs/sources",
    "docs/decisions",
    "docs/checklists",
    "tests/fixtures/campaign",
)
# Private files, matched by name anywhere in the tree.
PRIVATE_FILE_NAMES = {
    "sources.yml",
    "campaign-sources.yml",
    "source-leads.yml",
    "manual-events.yml",
    "removals.yml",
    "site.yml",
    "PROJECT.md",
    "STATUS.md",
    "QUESTIONS.md",
}


# Placeholder files whose content is the same in any repo.
PLACEHOLDER_NAMES = {".gitkeep", ".keep"}

# Files the two repos share on purpose (identical test code). The content
# comparison skips them; everything else in the private repo is compared.
SHARED_ON_PURPOSE = ("tests/guards/", "tests/test_licences.py", "tests/test_workflows.py")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _blocked_reason(path: str) -> str | None:
    """Layer 2: why a path is on the block list, or None."""
    p = PurePosixPath(path)
    parts = p.parts
    if not parts:
        return None
    if parts[0] in PRIVATE_TOP_FOLDERS:
        return f"private folder {parts[0]}/"
    for sub in PRIVATE_SUB_FOLDERS:
        if path == sub or path.startswith(sub + "/"):
            return f"private folder {sub}/"
    name = p.name
    if name == ".env" or name.startswith(".env."):
        return ".env file"
    if name in PRIVATE_FILE_NAMES:
        return f"private file name {name}"
    return None


def _allowed(path: str) -> bool:
    """Layer 1: is the path on the public repo's allow list?"""
    if path in PUBLIC_ALLOWED_FILES:
        return True
    if path.startswith(PUBLIC_ALLOWED_FOLDERS):
        return True
    return any(pattern.match(path) for pattern in PUBLIC_ALLOWED_PATTERNS)


def forbidden_reason(path: str) -> str | None:
    """Why this path may not be in the public repo, or None if it may."""
    blocked = _blocked_reason(path)
    if blocked:
        return blocked
    if not _allowed(path):
        return "not on the public repo's allow list"
    return None


def tracked_files(repo: Path) -> list[str]:
    """Committed files plus new files not yet committed (but not ignored ones)."""
    out = _git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    return sorted({line for line in out.split("\0") if line})


def history_files(repo: Path) -> set[str]:
    """Every path that has ever existed in any commit on any branch."""
    out = _git(repo, "log", "--all", "--name-only", "--format=", "--no-renames")
    return {line.strip() for line in out.splitlines() if line.strip()}


def all_blob_ids(repo: Path) -> set[str]:
    """Every file content (git blob id) ever stored in the repo."""
    out = _git(repo, "rev-list", "--all", "--objects")
    ids = {line.split(" ", 1)[0] for line in out.splitlines() if line}
    if not ids:
        return set()
    typed = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "--batch-check=%(objectname) %(objecttype)"],
        input="\n".join(sorted(ids)),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {line.split()[0] for line in typed.splitlines() if line.endswith(" blob")}


def private_blob_ids(private_repo: Path) -> dict[str, str]:
    """Blob ids of every file in the private repo, mapped to path.

    Skipped: the test files shared on purpose, placeholder files (`.gitkeep`)
    and empty files, whose content is the same everywhere and says nothing.
    """
    found: dict[str, str] = {}
    for path in tracked_files(private_repo):
        if path.startswith(SHARED_ON_PURPOSE):
            continue
        full = private_repo / path
        if full.name in PLACEHOLDER_NAMES or not full.is_file() or full.stat().st_size == 0:
            continue
        blob = _git(private_repo, "hash-object", "--", path).strip()
        found[blob] = path
    return found


def find_leaks(public_repo: Path, private_repo: Path | None = None) -> list[str]:
    problems: list[str] = []
    for path in tracked_files(public_repo):
        reason = forbidden_reason(path)
        if reason:
            problems.append(f"{path}: {reason} (in the current files)")
    history = history_files(public_repo) if has_commits(public_repo) else set()
    for path in sorted(history):
        reason = forbidden_reason(path)
        if reason:
            problems.append(f"{path}: {reason} (in the git history)")
    if private_repo is not None:
        public_blobs = all_blob_ids(public_repo)
        for blob, path in sorted(private_blob_ids(private_repo).items()):
            if blob in public_blobs:
                problems.append(
                    f"private file {path} has an exact copy in the public repo or its history"
                )
    return sorted(set(problems))


# ---------------------------------------------------------------------------
# 2. Secret scan
# ---------------------------------------------------------------------------

ALLOW_MARKER = "pv-secret-scan: allow"


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]
    value_group: int = 0  # which group holds the secret-looking value
    value_filter: str = "key"  # "key": must look like a random key; "password": any real word


RULES = (
    Rule("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    Rule("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    Rule("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    Rule("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b")),
    Rule("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    Rule("OpenAI-style key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}\b")),
    Rule("Resend API key", re.compile(r"\bre_[A-Za-z0-9]{6,}_[A-Za-z0-9]{12,}\b")),
    Rule("Supabase secret key", re.compile(r"\bsb_secret_[A-Za-z0-9_\-]{16,}")),
    Rule(
        "JSON web token (for example a Supabase key)",
        re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    ),
    Rule("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}")),
    Rule("Stripe live key", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}")),
    Rule("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    Rule(
        "key, token or password assigned a value",
        re.compile(
            r"(?i)\b[\w\-]*(?:api[_\-]?key|secret|token|passw(?:or)?d|service[_\-]?role[_\-]?key)"
            r"[\w\-]*[\"']?\s*[:=]\s*[\"']?([^\s\"'#,;]{16,})"
        ),
        value_group=1,
    ),
    Rule(
        "password written into a web address (scheme://user:password@host)",
        re.compile(r"\b[A-Za-z][A-Za-z0-9+.\-]*://[^\s/:@\"'<>]*:([^\s/@\"'<>]+)@[A-Za-z0-9\[]"),
        value_group=1,
        value_filter="password",
    ),
)

# Stand-in passwords in documentation, never real ones.
PLACEHOLDER_PASSWORDS = {
    "password",
    "pass",
    "passwd",
    "pw",
    "pwd",
    "secret",
    "token",
    "user",
    "username",
    "x",
    "xxx",
    "***",
    "...",
    "changeme",
    "example",
}

PLACEHOLDER_WORDS = ("example", "placeholder", "changeme", "your", "xxxx", "dummy", "redacted")


def _looks_real(value: str) -> bool:
    """Filter for the generic rule: a real key mixes letters and digits."""
    low = value.lower()
    if any(word in low for word in PLACEHOLDER_WORDS):
        return False
    if value.startswith(("$", "<", "{", "%")) or "${" in value:
        return False
    if "(" in value or value.startswith(("os.", "env.", "secrets.", "process.")):
        return False  # code that reads a secret, not a secret
    has_digit = any(c.isdigit() for c in value)
    has_alpha = any(c.isalpha() for c in value)
    return has_digit and has_alpha and len(set(value)) >= 8


def _looks_like_real_password(value: str) -> bool:
    """Filter for passwords in web addresses: skip obvious stand-ins."""
    low = value.lower()
    if low in PLACEHOLDER_PASSWORDS or set(value) <= set("*x.X"):
        return False
    if any(word in low for word in PLACEHOLDER_WORDS):
        return False
    # A variable filled in at run time is not a password.
    return not (value.startswith(("$", "<", "{", "%", "[")) or "${" in value)


def _value_is_real(rule: Rule, value: str) -> bool:
    if rule.value_filter == "password":
        return _looks_like_real_password(value)
    return _looks_real(value)


@dataclass(frozen=True)
class Finding:
    where: str  # "path:line" or "commit abc1234 path"
    rule: str

    def __str__(self) -> str:  # never includes the matched text
        return f"{self.where}: possible {self.rule}"


def scan_text(text: str) -> list[tuple[int, str]]:
    """Return (line number, rule name) for every hit in text."""
    hits: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARKER in line:
            continue
        for rule in RULES:
            for match in rule.pattern.finditer(line):
                if rule.value_group and not _value_is_real(rule, match.group(rule.value_group)):
                    continue
                hits.append((number, rule.name))
                break
    return hits


def _read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None  # binary file
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def scan_tree(repo: Path) -> list[Finding]:
    findings: list[Finding] = []
    for rel in tracked_files(repo):
        full = repo / rel
        if not full.is_file():
            continue  # deleted in the working copy
        text = _read_text(full)
        if text is None:
            continue
        for line, rule in scan_text(text):
            findings.append(Finding(f"{rel}:{line}", rule))
    return findings


class GitError(RuntimeError):
    """A git command failed, so the scan could not be completed."""


def _git_bytes(repo: Path, *args: str) -> bytes:
    """Run git and return its output. Any failure raises GitError: a scan that
    could not run must fail, never pass as clean."""
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)
    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="replace").strip().splitlines()
        raise GitError(f"git {args[0]} failed in {repo}: {error[-1] if error else 'no message'}")
    return result.stdout


def has_commits(repo: Path) -> bool:
    """False only for a repo with no commits at all (the one case history may be skipped)."""
    return bool(_git_bytes(repo, "rev-list", "--all", "--max-count=1").strip())


def scan_history(repo: Path) -> list[Finding]:
    """Scan every line ever added in any commit on any branch, every commit
    message, and everything reachable from a tag."""
    # --diff-merges=first-parent: without it git log shows no diff for merge
    # commits, so a key added while resolving a merge would never be seen.
    out = _git_bytes(
        repo,
        "log",
        "--all",
        "-p",
        "--diff-merges=first-parent",
        "--no-color",
        "--no-ext-diff",
        "--format=commit %h",
        "--unified=0",
    )
    findings: list[Finding] = []
    commit = "?"
    path = "?"
    for raw in out.decode("utf-8", errors="replace").splitlines():
        if raw.startswith("commit "):
            commit = raw.split(" ", 1)[1]
        elif raw.startswith("+++ "):
            path = raw[6:] if raw.startswith("+++ b/") else raw[4:]
        elif raw.startswith("+") and not raw.startswith("+++"):
            for _, rule in scan_text(raw[1:]):
                findings.append(Finding(f"commit {commit} {path}", rule))
    return findings + scan_commit_messages(repo) + scan_tags(repo)


def scan_commit_messages(repo: Path) -> list[Finding]:
    """Scan the full message of every commit on any branch or fetched ref."""
    out = _git_bytes(repo, "log", "--all", "--format=%x00%h%x00%B")
    findings: list[Finding] = []
    records = out.decode("utf-8", errors="replace").split("\0")[1:]
    for commit, message in zip(records[0::2], records[1::2], strict=False):
        for _, rule in scan_text(message):
            findings.append(Finding(f"commit {commit} message", rule))
    return findings


def _scan_object_text(repo: Path, object_id: str, where: str) -> list[Finding]:
    text = _git_bytes(repo, "cat-file", "-p", object_id)
    if b"\0" in text[:8192]:
        return []  # binary
    return [Finding(where, rule) for _, rule in scan_text(text.decode("utf-8", errors="replace"))]


def scan_tags(repo: Path) -> list[Finding]:
    """Follow every tag to what it points at and scan along the way.

    - A tag object (annotated tag): its whole text, including the message. A
      tag can point to another tag; every tag in the chain is read.
    - A blob (a file stored without a commit): its contents.
    - A tree (a folder stored without a commit): every file in it.
    - A commit: already covered by the commit scans above.
    """
    out = _git_bytes(repo, "for-each-ref", "refs/tags", "--format=%(refname:short)%00%(objectname)")
    findings: list[Finding] = []
    for line in out.decode("utf-8", errors="replace").splitlines():
        if not line:
            continue
        tag, object_id = line.split("\0", 1)
        seen: set[str] = set()
        label = f"tag {tag}"
        while object_id and object_id not in seen:
            seen.add(object_id)
            kind = _git_bytes(repo, "cat-file", "-t", object_id).decode().strip()
            if kind == "tag":
                findings += _scan_object_text(repo, object_id, f"{label} message")
                body = _git_bytes(repo, "cat-file", "-p", object_id).decode("utf-8", "replace")
                target = re.search(r"^object ([0-9a-f]{40,64})$", body, re.MULTILINE)
                object_id = target.group(1) if target else ""
                label = f"tag {tag} (inner tag {object_id[:7]})"
            elif kind == "blob":
                findings += _scan_object_text(repo, object_id, f"tag {tag} file {object_id[:7]}")
                break
            elif kind == "tree":
                listing = _git_bytes(repo, "ls-tree", "-r", "-z", object_id)
                for entry in listing.decode("utf-8", "replace").split("\0"):
                    if not entry:
                        continue
                    meta, path = entry.split("\t", 1)
                    entry_kind, entry_id = meta.split()[1:3]
                    if entry_kind == "blob":
                        findings += _scan_object_text(
                            repo, entry_id, f"tag {tag} folder file {path}"
                        )
                break
            else:
                break  # commit: covered by scan_history and scan_commit_messages
    return findings


def find_secrets(repo: Path, history: bool = True) -> list[Finding]:
    """Scan files, and the history unless history=False. Raises GitError if
    any git command fails; a repo with no commits yet has no history to scan."""
    findings = scan_tree(repo)
    if history and has_commits(repo):
        findings += scan_history(repo)
    return sorted(set(findings), key=str)


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    leaks = sub.add_parser("leaks", help="check the public repo for private files")
    leaks.add_argument("public_repo", type=Path)
    leaks.add_argument(
        "--private", type=Path, default=None, help="private repo, for content checks"
    )
    secrets = sub.add_parser("secrets", help="scan a repo for key-shaped text")
    secrets.add_argument("repo", type=Path)
    secrets.add_argument("--no-history", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "leaks":
        problems = find_leaks(args.public_repo, args.private)
        label = "Private material found in the public repo"
    else:
        problems = [str(f) for f in find_secrets(args.repo, history=not args.no_history)]
        label = "Possible secrets found (values not shown)"
    if problems:
        print(f"{label}:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
