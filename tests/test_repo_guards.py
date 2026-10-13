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
        "DATABASE_URL=postgresql://postgres:" + "Tr0ub4dor-" + "horse@db.invented.supabase.co:5432/db",
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
