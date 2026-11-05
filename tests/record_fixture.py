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

To record from a page already fetched once with `python -m pvscrapers.fetch`
(so nothing is fetched twice), add `--page <that file>`. The fetch command
writes `<that file>.fetch.json` beside it, the proof of how it was fetched;
the recorder refuses a page without one, or one that does not show the
source's own address, HTTP 200, robots.txt read and allowing it, our bot, and
at least the source's crawl_delay_seconds (pass the same number to the fetch
command as --crawl-delay). The time and those facts go into fetched.json.

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

from pvscrapers import __version__, html, scrapers
from pvscrapers.fetch import BOT_NAME, SIDECAR_SUFFIX, Fetcher, FetchError

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


_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_ALWAYS_REMOVE = frozenset({"script", "style", "img", "svg", "iframe", "form", "noscript", "p"})


def _html_excerpt(
    text: str, tag: str, cls: str, *, also_remove_class: str | tuple[str, ...] = ()
) -> tuple[str, dict[str, int]]:
    """Keep only the <tag class=cls> elements a page scraper reads, without prose
    paragraphs, images, scripts, forms or email links."""
    page = html.parse(text)
    keep = page.find_all(tag, cls)
    removed: dict[str, int] = {"page outside the parts the scraper reads": 1}
    for node in keep:
        for name in _ALWAYS_REMOVE:
            n = len(node.find_all(name))
            if n:
                removed[f"<{name}>"] = removed.get(f"<{name}>", 0) + n
        node.remove(_ALWAYS_REMOVE)
        extra = (also_remove_class,) if isinstance(also_remove_class, str) else also_remove_class
        for name in extra:
            n = len(node.find_all(cls=name))
            if n:
                removed[f".{name}"] = removed.get(f".{name}", 0) + n
            node.remove(cls=name)
        for link in node.find_all("a"):
            if link.attrs.get("href", "").startswith("mailto:"):
                del link.attrs["href"]
                link.children = ["(email removed)"]
                removed["email links"] = removed.get("email links", 0) + 1
    cleaned = html.document(
        keep, "Excerpt: only the parts the scraper reads; see fetched.json for what was removed."
    )
    if _EMAIL.search(cleaned):
        raise Refused("an email address is still in the cleaned page; clean it by hand")
    return cleaned, removed


def clean_accordion(text: str) -> tuple[str, dict[str, int]]:
    return _html_excerpt(text, "div", "accordion")


def clean_bl_events(text: str) -> tuple[str, dict[str, int]]:
    return _html_excerpt(text, "article", "the-event")


def clean_apostrophe(text: str) -> tuple[str, dict[str, int]]:
    return _html_excerpt(
        text, "div", "apostrophe-event-preview", also_remove_class="apostrophe-event-body"
    )


def clean_mec(text: str) -> tuple[str, dict[str, int]]:
    """MEC list: also drops the organizer block (a person's name) and descriptions."""
    return _html_excerpt(
        text,
        "div",
        "mec-event-list-standard",
        also_remove_class=("mec-shortcode-organizers", "mec-event-description", "mec-event-image"),
    )


# Scraper name -> (page file extension, cleaner). A scraper with no cleaner
# cannot be recorded until one is added here.
CLEANERS = {
    "tec_ical": (".ics", clean_ical),
    "accordion_event_list": (".html", clean_accordion),
    "bl_events": (".html", clean_bl_events),
    "apostrophe_events": (".html", clean_apostrophe),
    "mec_events": (".html", clean_mec),
}


class Refused(Exception):
    """The tool will not record this source."""


def check_recordable(source: dict) -> None:
    if source.get("sensitive") is not False:
        raise Refused("source is not marked sensitive: false; invent this fixture by hand")
    if source.get("default_type") in ("campaign", "protest_action"):
        raise Refused("campaign and protest sources are never recorded; invent this fixture")
    if source.get("scraper") not in CLEANERS:
        raise Refused(f"no fixture cleaner for scraper {source.get('scraper')!r} yet")


def check_fetch_record(source: dict, page_file: Path) -> dict:
    """The fetch command's record beside a saved page, checked against the source."""
    sidecar = page_file.with_name(page_file.name + SIDECAR_SUFFIX)
    try:
        proof = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Refused(
            f"no fetch record beside {page_file.name}; fetch the page with "
            "python -m pvscrapers.fetch --out (or --out-dir), which writes one"
        ) from None
    robots = proof.get("robots_txt") or {}
    wanted_delay = float(source.get("crawl_delay_seconds") or 0)
    problems = []
    if proof.get("url") != source.get("url"):
        problems.append("it is not the source's own address")
    if proof.get("status") != 200:
        problems.append("the page did not answer HTTP 200")
    if not str(proof.get("bot", "")).startswith(f"{BOT_NAME}/"):
        problems.append("it was not fetched by our bot")
    if robots.get("verdict") != "allowed" or not robots.get("read_at"):
        problems.append("robots.txt was not read and found allowing")
    if float(proof.get("source_crawl_delay_seconds") or 0) < wanted_delay:
        problems.append(f"the source's crawl_delay_seconds ({wanted_delay:g}) was not kept")
    try:
        when = datetime.fromisoformat(str(proof.get("fetched_at")))
        if when.tzinfo is None:
            raise ValueError
    except ValueError:
        problems.append("its fetch time cannot be read")
    if problems:
        raise Refused(f"the fetch record does not fit: {'; '.join(problems)}")
    keep = ("url", "final_url", "status", "fetched_at", "bot", "robots_txt", "delay_seconds")
    return {k: proof[k] for k in keep if k in proof} | {
        "source_crawl_delay_seconds": proof.get("source_crawl_delay_seconds", 0)
    }


def record(
    source: dict,
    fetcher: Fetcher | None,
    out: Path,
    *,
    replace: bool = False,
    now: datetime | None = None,
    page_file: Path | None = None,
) -> dict:
    """Fetch (or take `page_file`, fetched once with the polite command, with its
    fetch record beside it), clean and write one fixture. Returns a short summary."""
    check_recordable(source)
    extension, cleaner = CLEANERS[source["scraper"]]
    page = out / f"page{extension}"
    if page.exists() and not replace:
        raise Refused(f"{page} exists; pass --replace to record over it")

    proof = None
    if page_file is None:
        if fetcher is None:
            raise Refused("no fetcher and no page")
        text = fetcher.fetch_source(source).text()
        how = "Fetched once with tests/record_fixture.py"
        fetched_at = (now or datetime.now().astimezone()).isoformat(timespec="seconds")
    else:
        proof = check_fetch_record(source, page_file)
        text = page_file.read_text(encoding="utf-8")
        how = "Fetched once with python -m pvscrapers.fetch, then cleaned with tests/record_fixture.py"
        fetched_at = proof["fetched_at"]
    cleaned, removed = cleaner(text)

    out.mkdir(parents=True, exist_ok=True)
    page.write_bytes(cleaned.encode("utf-8"))
    removed_text = ", ".join(f"{n} {name}" for name, n in sorted(removed.items())) or "nothing"
    (out / "fetched.json").write_text(
        json.dumps(
            {
                "fetched_at": fetched_at,
                "how": f"{how} ({BOT_NAME}/{__version__}, contact "
                "address from the city's settings), robots.txt read first, crawl delays honoured.",
                "changed_after_fetch": f"Removed: {removed_text}. "
                + (
                    "Descriptions became a placeholder. "
                    if extension == ".ics"
                    else "Kept only the parts the scraper reads. "
                )
                + "Check by eye that no person's name remains.",
                "source_json": "Invented. Only the page itself is a recorded copy.",
                **({"fetch_record": proof} if proof else {}),
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
    parser.add_argument(
        "--page", type=Path, help="a page saved by python -m pvscrapers.fetch (record beside it)"
    )
    args = parser.parse_args(argv)

    fetcher = None
    if not args.page:
        try:
            fetcher = Fetcher(os.environ.get("PV_CONTACT_EMAIL", ""))
        except ValueError:
            print("Not recorded: set PV_CONTACT_EMAIL to the city's contact address.")
            return 1
    try:
        source = json.loads(args.source.read_text(encoding="utf-8"))
        summary = record(source, fetcher, args.out, replace=args.replace, page_file=args.page)
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
