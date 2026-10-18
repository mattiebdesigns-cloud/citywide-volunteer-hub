"""Public-repo safety checks (PROJECT.md sections 3 and 13; CLAUDE.md "Never commit here").

- No private folder, source list or .env file in this repo, now or in its history.
- No key-shaped text in tracked files or in the history.
- The checkers themselves catch what they should (self-tests with invented keys).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from guards import repo_guard

ROOT = Path(__file__).resolve().parent.parent


def test_no_private_files_in_public_repo():
    problems = repo_guard.find_leaks(ROOT)
    assert not problems, "\n".join(problems)


def test_no_secrets_in_files_or_history():
    findings = repo_guard.find_secrets(ROOT, history=True)
    assert not findings, "\n".join(str(f) for f in findings)


@pytest.mark.parametrize(
    "path",
    [
        "config/site.yml",
        "supabase/migrations/001.sql",
        "support/kb/faq.md",
        "outreach/drafts/a.md",
        "web/src/pages/index.astro",
        "docs/sources/some-source.md",
        ".env",
        "site/.env.local",
        "pvscrapers/sources.yml",
        "anything/campaign-sources.yml",
        "tests/fixtures/campaign/page.html",
        "site/site.yml",
        # Not on the allow list: private-repo files and folders.
        ".claude/agents/x.md",
        "IDEAS.md",
        "docs/OWNER-SETUP.md",
        "docs/market/x.md",
        "docs/RESEARCH-SCHEDULE.md",
        "pipeline/x.py",
        "schema/x.json",
        "data/x.json",
        "docs/sub/x.schema.json",
        "notes.txt",
    ],
)
def test_leak_check_flags_private_paths(path: str):
    assert repo_guard.forbidden_reason(path)


@pytest.mark.parametrize(
    "path",
    [
        "pvscrapers/platforms/example.py",
        "site/src/config/filters.ts",
        "site/src/i18n/en.json",
        "docs/EVENT-FORMAT.md",
        "docs/design.md",
        "docs/event.schema.json",
        "docs/examples/events.sample.json",
        "tests/fixtures/example/page.html",
        ".github/workflows/ci.yml",
        "README.md",
        "LICENSE",
        "CONTRIBUTING.md",
        "CLAUDE.md",
        "pyproject.toml",
        "uv.lock",
        ".gitignore",
    ],
)
def test_leak_check_allows_public_paths(path: str):
    assert repo_guard.forbidden_reason(path) is None


# Invented key-shaped strings, assembled at run time so this file itself
# never contains anything that looks like a key.
FAKE = "Ab3dE5gH7jK9mN1pQ2rS4tU6vW8xY0zA"


@pytest.mark.parametrize(
    "line",
    [
        "-----BEGIN " + "RSA PRIVATE KEY-----",
        "AKIA" + "ABCDEFGHIJKLMNOP",
        "token: gh" + "p_" + FAKE + "1234",
        "ANTHROPIC_API_KEY=sk-" + "ant-" + FAKE,
        "RESEND_API_KEY=re" + "_Ab3dE5gH_" + FAKE,
        "eyJ" + "hbGciOiJIUzI1NiJ9.eyJ" + "yb2xlIjoic2VydmljZSJ9." + FAKE,
        "SUPABASE_SERVICE_ROLE_KEY=" + FAKE,
        'password = "' + FAKE + '"',
        "DATABASE_URL=postgresql://postgres:"
        + "Tr0ub4dor-"
        + "horse@db.invented.supabase.co:5432/db",
        "git clone https://bot:" + FAKE[:12] + "@github.com/owner/repo",
        "REDIS_URL=redis://:" + FAKE[:14] + "@cache.invented.org:6379",
    ],
)
def test_secret_scan_catches_invented_keys(line: str):
    assert repo_guard.scan_text(line), "scanner missed an invented key"


@pytest.mark.parametrize(
    "line",
    [
        "ANTHROPIC_API_KEY=",
        "RESEND_API_KEY=${{ secrets.RESEND_API_KEY }}",
        "key = os.environ.get('ANTHROPIC_API_KEY')",
        "SUPABASE_ANON_KEY=your-anon-key-here-1234",
        'hash = "sha256:' + "0" * 64 + '"',
        "Respect robots.txt and each site's terms.",
        "postgresql://user:pw@x.supabase.com",
        "https://user:token@github.com/owner/repo",
        "postgresql://user:password@localhost:5432/db",
        "https://x-access-token:${{ secrets.TOKEN }}@github.com/owner/repo",
        "postgres://app:${DB_PASSWORD}@localhost/db",
        "https://example.org/events?a=b:c@d",
        "mailto:someone@example.org",
    ],
)
def test_secret_scan_ignores_ordinary_lines(line: str):
    assert not repo_guard.scan_text(line)


def test_secret_scan_never_reports_the_value(tmp_path):
    secret = "Tr0ub4dor-" + "horse"
    (tmp_path / "settings.txt").write_text("DB=postgresql://app:" + secret + "@db.invented.org/x\n")
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    findings = repo_guard.find_secrets(tmp_path, history=False)
    assert findings, "scanner missed the invented password"
    assert all(secret not in str(f) for f in findings)


def test_secret_scan_reads_commit_messages(tmp_path):
    import subprocess

    key = "sk-" + "ant-" + FAKE
    git = ["git", "-C", str(tmp_path), "-c", "user.name=Test", "-c", "user.email=test@example.org"]
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "notes.txt").write_text("nothing secret here\n")
    subprocess.run([*git, "add", "notes.txt"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "Add notes\n\nused key " + key], check=True)
    findings = [str(f) for f in repo_guard.find_secrets(tmp_path, history=True)]
    assert any(f.startswith("commit ") and " message: " in f for f in findings), findings
    assert all(key not in f and FAKE not in f for f in findings)


def test_secret_scan_reads_tag_messages(tmp_path):
    import subprocess

    key = "sk-" + "ant-" + FAKE
    git = ["git", "-C", str(tmp_path), "-c", "user.name=Test", "-c", "user.email=test@example.org"]
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "notes.txt").write_text("nothing secret here\n")
    subprocess.run([*git, "add", "notes.txt"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "Add notes"], check=True)
    subprocess.run([*git, "tag", "-a", "v0.0.1", "-m", "Release\n\nkey " + key], check=True)
    findings = [str(f) for f in repo_guard.find_secrets(tmp_path, history=True)]
    assert any(f.startswith("tag v0.0.1 message: ") for f in findings), findings
    assert all(key not in f and FAKE not in f for f in findings)


def _new_repo(tmp_path, with_commit=True):
    import subprocess

    git = ["git", "-C", str(tmp_path), "-c", "user.name=Test", "-c", "user.email=test@example.org"]
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    if with_commit:
        (tmp_path / "notes.txt").write_text("nothing secret here\n")
        subprocess.run([*git, "add", "notes.txt"], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "Add notes"], check=True)
    return git


def test_empty_repo_scans_clean(tmp_path):
    _new_repo(tmp_path, with_commit=False)
    assert repo_guard.find_secrets(tmp_path, history=True) == []


def test_git_failure_fails_the_scan(tmp_path, monkeypatch):
    _new_repo(tmp_path)
    real = repo_guard._git_bytes

    def broken(repo, *args):
        if args[0] == "log":
            return real(repo, "log", "--no-such-option")
        return real(repo, *args)

    monkeypatch.setattr(repo_guard, "_git_bytes", broken)
    with pytest.raises(repo_guard.GitError):
        repo_guard.find_secrets(tmp_path, history=True)


def test_not_a_repo_fails_the_scan(tmp_path):
    with pytest.raises(Exception):  # noqa: B017 (any failure is right; passing clean is wrong)
        repo_guard.find_secrets(tmp_path, history=True)


def test_secret_scan_follows_nested_tags(tmp_path):
    import subprocess

    key = "sk-" + "ant-" + FAKE
    git = _new_repo(tmp_path)
    subprocess.run([*git, "tag", "-a", "inner", "-m", "key " + key], check=True)
    subprocess.run(
        [*git, "tag", "-a", "outer", "-m", "Outer tag", "inner"], check=True, capture_output=True
    )
    subprocess.run([*git, "tag", "-d", "inner"], check=True, capture_output=True)
    findings = [str(f) for f in repo_guard.find_secrets(tmp_path, history=True)]
    assert any(f.startswith("tag outer (inner tag ") for f in findings), findings
    assert all(FAKE not in f for f in findings)


def test_secret_scan_reads_tagged_file_and_folder(tmp_path):
    import subprocess

    key = "sk-" + "ant-" + FAKE
    git = _new_repo(tmp_path)
    blob = subprocess.run(
        [*git, "hash-object", "-w", "--stdin"],
        input="KEY=" + key + "\n",
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    tree = subprocess.run(
        [*git, "mktree"],
        input=f"100644 blob {blob}\tsecret.env\n",
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run([*git, "tag", "just-a-file", blob], check=True)
    subprocess.run([*git, "tag", "just-a-folder", tree], check=True)
    findings = [str(f) for f in repo_guard.find_secrets(tmp_path, history=True)]
    assert any(f.startswith("tag just-a-file file ") for f in findings), findings
    assert any(f.startswith("tag just-a-folder folder file secret.env") for f in findings), findings
    assert all(FAKE not in f for f in findings)


def test_secret_scan_reads_merge_commits(tmp_path):
    import subprocess

    key = "sk-" + "ant-" + FAKE
    git = _new_repo(tmp_path)

    def run(*args):
        subprocess.run([*git, *args], check=True, capture_output=True)

    base = subprocess.run(
        [*git, "rev-parse", "--abbrev-ref", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    run("checkout", "-q", "-b", "side")
    (tmp_path / "side.txt").write_text("side branch work\n")
    run("add", "side.txt")
    run("commit", "-q", "-m", "Side work")
    run("checkout", "-q", base)
    (tmp_path / "main.txt").write_text("main branch work\n")
    run("add", "main.txt")
    run("commit", "-q", "-m", "Main work")
    # Merge, and slip a key into the merge commit itself.
    run("merge", "--no-commit", "--no-ff", "side")
    (tmp_path / "config.txt").write_text("KEY=" + key + "\n")
    run("add", "config.txt")
    run("commit", "-q", "-m", "Merge side")
    # Remove it in the next commit, so only the history still has it.
    (tmp_path / "config.txt").write_text("KEY=\n")
    run("add", "config.txt")
    run("commit", "-q", "-m", "Remove key")
    findings = [str(f) for f in repo_guard.find_secrets(tmp_path, history=True)]
    assert len(findings) == 1, findings
    assert findings[0].startswith("commit ") and "config.txt" in findings[0]
    assert FAKE not in findings[0]


def test_secret_scan_skips_ignored_files_but_not_committed_ones(tmp_path):
    import subprocess

    key = "sk-" + "ant-" + FAKE
    git = _new_repo(tmp_path)
    (tmp_path / ".gitignore").write_text("node_modules/\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "package.js").write_text("key = '" + key + "'\n")
    assert repo_guard.find_secrets(tmp_path, history=False) == []
    # A file forced into git despite the ignore rule is still scanned.
    (tmp_path / "node_modules" / "forced.js").write_text("key = '" + key + "'\n")
    subprocess.run([*git, "add", "-f", "node_modules/forced.js"], check=True)
    findings = [str(f) for f in repo_guard.find_secrets(tmp_path, history=False)]
    assert findings == ["node_modules/forced.js:1: possible Anthropic API key"], findings
