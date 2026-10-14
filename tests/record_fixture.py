"""Record one public calendar page as a scraper fixture (PROJECT.md section 4).

Fetches the page ONCE with the polite fetcher, through `Fetcher.fetch_source`,
so robots.txt is read first, the named bot and contact address are sent, and
the longest of the site's Crawl-delay and the source's own
`crawl_delay_seconds` is waited. Then it removes everything a fixture must not
hold (descriptions, images, organizer, attendee and contact fields) and writes:

    <out>/page.<ext>     the cleaned copy
    <out>/fetched.json   when it was fetched and what was removed (no address, no contact)

If <out>/source.json already exists (an INVENTED source entry you wrote), it
also writes expected.json and dropped.json from the scraper's output. Read
both before committing: they are what the tests will hold the scraper to.

The recorded page is a copy of a public calendar and is not covered by this
repo's MIT licence; nor are the publisher's titles, places, times and links in
expected.json and dropped.json. On the publisher's request the whole case
folder is deleted (tests/fixtures/NOTICE.md).

Never record a sensitive or campaign source: the tool refuses any source entry
that is not marked `sensitive: false`, or whose type is campaign or
protest_action. Invent fixtures for those by hand.

Usage, from the repo folder:

    PV_CONTACT_EMAIL=<city contact> uv run python tests/record_fixture.py \\
        --source /path/outside/this/repo/entry.json \\
        --out tests/fixtures/<scraper>/<case>

`entry.json` is the real source entry (from the city's private list) as JSON.
Keep it outside this repo. The contact address is read from the environment
variable and never printed or written.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from pvscrapers import __version__, scrapers
from pvscrapers.fetch import BOT_NAME, Fetcher, FetchError

# Properties a fixture never keeps. DESCRIPTION is replaced by a placeholder
# so the fixture still shows the scraper ignores it.
ICAL_REMOVE = ("DESCRIPTION", "X-ALT-DESC", "ATTACH", "ORGANIZER", "ATTENDEE", "CONTACT", "COMMENT")
ICAL_PLACEHOLDER = "DESCRIPTION:(removed from this fixture; the scraper never reads descriptions)"


def clean_ical(text: str) -> tuple[str, dict[str, int]]:
    """Remove ICAL_REMOVE properties, including their folded continuation lines."""
    out: list[str] = []
    removed: dict[str, int] = {}
    skipping = False
    for line in text.replace("\r\n", "\n").split("\n"):
        if line[:1] in (" ", "\t"):
            if not skipping:
                out.append(line)
            continue
        name = re.split(r"[;:]", line, maxsplit=1)[0].upper()
        skipping = name in ICAL_REMOVE
        if skipping:
            removed[name] = removed.get(name, 0) + 1
            if name == "DESCRIPTION":
                out.append(ICAL_PLACEHOLDER)
            continue
        out.append(line)
    return "\r\n".join(out), removed


# Scraper name -> (page file extension, cleaner). A scraper with no cleaner
# cannot be recorded until one is added here.
CLEANERS = {"tec_ical": (".ics", clean_ical)}


class Refused(Exception):
    """The tool will not record this source."""


def check_recordable(source: dict) -> None:
    if source.get("sensitive") is not False:
        raise Refused("source is not marked sensitive: false; invent this fixture by hand")
    if source.get("default_type") in ("campaign", "protest_action"):
        raise Refused("campaign and protest sources are never recorded; invent this fixture")
    if source.get("scraper") not in CLEANERS:
        raise Refused(f"no fixture cleaner for scraper {source.get('scraper')!r} yet")


def record(
    source: dict, fetcher: Fetcher, out: Path, *, replace: bool = False, now: datetime | None = None
) -> dict:
    """Fetch, clean and write one fixture. Returns a short summary."""
    check_recordable(source)
    extension, cleaner = CLEANERS[source["scraper"]]
    page = out / f"page{extension}"
    if page.exists() and not replace:
        raise Refused(f"{page} exists; pass --replace to record over it")

    response = fetcher.fetch_source(source)
    fetched_at = (now or datetime.now().astimezone()).isoformat(timespec="seconds")
    cleaned, removed = cleaner(response.text())

    out.mkdir(parents=True, exist_ok=True)
    page.write_bytes(cleaned.encode("utf-8"))
    removed_text = ", ".join(f"{n} {name}" for name, n in sorted(removed.items())) or "nothing"
    (out / "fetched.json").write_text(
        json.dumps(
            {
                "fetched_at": fetched_at,
                "how": f"Fetched once with tests/record_fixture.py ({BOT_NAME}/{__version__}, contact "
                "address from the city's settings), robots.txt read first, crawl delays honoured.",
                "changed_after_fetch": f"Removed: {removed_text}. Descriptions became a placeholder. "
                "Check by eye that no person's name remains.",
                "source_json": "Invented. Only the page itself is a recorded copy.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = {"page": str(page), "removed": removed, "listings": None, "dropped": None}
    invented = out / "source.json"
    if invented.is_file():
        result = scrapers.get(source["scraper"]).parse_with_report(
            cleaned,
            json.loads(invented.read_text(encoding="utf-8")),
            datetime.fromisoformat(fetched_at),
        )
        (out / "expected.json").write_text(
            json.dumps(result.events, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (out / "dropped.json").write_text(
            json.dumps([asdict(d) for d in result.dropped], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        summary.update(listings=len(result.events), dropped=len(result.dropped))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", required=True, type=Path, help="real source entry, as JSON")
    parser.add_argument("--out", required=True, type=Path, help="tests/fixtures/<scraper>/<case>")
    parser.add_argument("--replace", action="store_true", help="record over an existing page")
    args = parser.parse_args(argv)

    try:
        fetcher = Fetcher(os.environ.get("PV_CONTACT_EMAIL", ""))
    except ValueError:
        print("Not recorded: set PV_CONTACT_EMAIL to the city's contact address.")
        return 1
    try:
        source = json.loads(args.source.read_text(encoding="utf-8"))
        summary = record(source, fetcher, args.out, replace=args.replace)
    except (Refused, FetchError, ValueError, OSError) as error:
        print(f"Not recorded: {error}")
        return 1
    print(f"Wrote {summary['page']}; removed {summary['removed'] or 'nothing'}.")
    if summary["listings"] is None:
        print(
            "Next: write an invented source.json in the same folder and run this again "
            "with --replace, or write expected.json by hand."
        )
    else:
        print(
            f"{summary['listings']} listings, {summary['dropped']} dropped. "
            "Read expected.json and dropped.json before committing."
        )
    print(
        "Reminder: the recorded page, and the publisher's titles, places, times and links in "
        "expected.json and dropped.json, are not covered by the MIT licence. If the publisher "
        "asks, delete the whole case folder. See tests/fixtures/NOTICE.md."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
