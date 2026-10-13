# Tests

## How to run them

You need [uv](https://docs.astral.sh/uv/). From the repo folder:

```sh
uv sync                              # installs the test tools
uv run pytest                        # runs every test
uv run ruff check .                  # lint
node site/src/i18n/check-keys.mjs    # English and Spanish interface text have the same keys
```

CI (`.github/workflows/ci.yml`) runs all four on every push and pull request.

## What the tests check

| File | What it checks |
|---|---|
| `test_event_schema.py` | Both schema files in `docs/` are valid. Every sample `events.json` matches the schema and has unique listing ids. The schema rejects listings it must reject (missing fields, guessed values, attendee lists, a protest action not marked sensitive). |
| `test_repo_guards.py` | Nothing that belongs only to a city's private setup is in this repo, now or in its history: source lists, settings files, `.env` files, private folders. No key-shaped text in any file or commit. |
| `test_licences.py` | Every Python package used is MIT, Apache-2.0, BSD, ISC or PSF-2.0. |
| `test_workflows.py` | Every GitHub Action is pinned to a fixed version; no workflow runs fork code with this repo's permissions, grants write access, or reads a secret. |

Paths in this repo must be on an allow list: `pvscrapers/`, `site/`, `tests/`, `.github/`, `docs/examples/`, `docs/EVENT-FORMAT.md`, `docs/*.schema.json`, and the root files `README.md`, `LICENSE`, `CONTRIBUTING.md`, `CLAUDE.md`, `pyproject.toml`, `uv.lock`, `.gitignore`. Some names are blocked even inside those folders, including `site.yml`, `sources.yml` and any `.env` file. A sample settings file must therefore have another name, for example `site/site.example.yml`.

The licence test checks every package in `uv.lock`, for every platform and Python version, by reading its licence from pypi.org. It needs the network.

`tests/guards/` holds the check code. A city's private repo keeps an identical copy and runs the same checks from its side.

The secret scan never prints what it found, only the file, line and kind of key. A line that is a known false alarm can carry `pv-secret-scan: allow`; reviewers check every use.

## Scraper fixtures (coming with the first scrapers)

Each scraper gets a folder `tests/fixtures/<scraper>/` with:

- `page.html` (or `.json`, `.ics`): a recorded copy of a public calendar page, **with every person's name removed**;
- `source.json`: an invented source entry with only what the scraper needs;
- `expected.json`: the listings the scraper should produce.

A test runs each scraper on its recorded page with the network off and checks that the output matches the schema and `expected.json`, has no field outside the schema (so no attendee or sign-up data), and is not empty.

## Rules

- Invented data only. Never put a real person's name or details in a fixture.
- A failing test blocks the merge. Do not skip or weaken a test to get green; say what is wrong in the pull request.
