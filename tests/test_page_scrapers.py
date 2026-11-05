"""The web-page scrapers (accordion_event_list, bl_events, apostrophe_events) and
their helpers, on small invented pages (PROJECT.md section 4). No network.

The recorded real pages are checked in test_scraper_fixtures.py; these cover
the rules those pages do not happen to show today.
"""

from __future__ import annotations

from datetime import UTC, datetime, time

import pytest

from pvscrapers import html, pagetext
from pvscrapers.core import SourceError
from pvscrapers.scrapers import accordion_event_list, apostrophe_events, bl_events, mec_events

READ_AT = datetime(2026, 11, 5, 17, 0, tzinfo=UTC)


def entry(scraper: str, **extra) -> dict:
    base = {
        "id": "example",
        "org_name": "Example Parks",
        "scraper": scraper,
        "url": "https://parks.example.org/",
        "area": "philadelphia",
        "listing_language": "en",
        "default_type": "service",
        "sensitive": False,
        "timezone": "America/New_York",
    }
    base.update(extra)
    return base


def reasons(result) -> dict[str, str]:
    return {d.title: d.reason for d in result.dropped}


# -- helpers --------------------------------------------------------------------


def test_html_reader_finds_elements_and_text():
    page = html.parse(
        '<div class="a b"><h2>Head &amp; more</h2><p>One<br>two</p></span><ul><li>x</ul></div>'
    )
    div = page.find("div", "b")
    assert div is not None and div.find("h2").text() == "Head & more"
    assert div.find("p").text() == "One two"
    assert [li.text() for li in page.find_all("li")] == ["x"]
    div.remove({"p"})
    assert "One" not in html.to_html(page)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("from 9:00 AM to 12:00 PM", (time(9), time(12))),
        ("9:00am – 10:00am", (time(9), time(10))),
        ("9:00 am - 12:00 pm", (time(9), time(12))),
        ("5:30 - 7:00 pm", (time(17, 30), time(19))),
        ("11:00 - 1:00 pm", (time(11), time(13))),
        ("All Day", None),
        ("9 am - noon", None),
    ],
)
def test_time_ranges(text, expected):
    assert pagetext.time_range(text) == expected


def test_page_scrapers_need_a_timezone():
    page = '<div class="accordion"><h2>Thursday</h2></div>'
    with pytest.raises(SourceError, match="timezone is required"):
        accordion_event_list.parse(page, entry("accordion_event_list", timezone=None), READ_AT)


# -- accordion_event_list -------------------------------------------------------

ACCORDION = """
<div class="accordion"><h2>Wednesday Stewardship (Weekly)</h2><div class="content"><ul>
 <li><a href="https://parks.example.org/event/crew-11-11-2026/">Trained Crew Day</a>
     <span>Wednesday, November 11, 2026 from 9:00 AM to 12:00 PM</span></li></ul></div></div>
<div class="accordion"><h2>Thursday Stewardship (Weekly)</h2><div class="content"><ul>
 <li><a href="https://parks.example.org/event/day-11-12-2026/">Thursday Service Day</a>
     <span>Thursday, November 12, 2026 from 9:00 AM to 12:00 PM</span></li>
 <li><a href="https://parks.example.org/event/day-11-12-2026/">Thursday Service Day</a>
     <span>Thursday, November 12, 2026 from 9:00 AM to 12:00 PM</span></li>
 <li><a href="https://parks.example.org/event/party/">Crew Leader Recruitment Party</a>
     <span>Saturday, November 14, 2026 from 12:00 PM to 2:00 PM</span></li>
 <li><a href="https://parks.example.org/event/tbd/">Date To Be Announced</a>
     <span>Thursday, December 3 from 9:00 AM to 12:00 PM</span></li></ul></div></div>
"""


def test_accordion_takes_only_the_sources_headings():
    source = entry(
        "accordion_event_list",
        require_headings=["Thursday Stewardship", "Saturday Stewardship"],
        drop_titles=["Recruitment"],
    )
    result = accordion_event_list.parse_with_report(ACCORDION, source, READ_AT)
    assert [(e["title"], e["start"], e["end"]) for e in result.events] == [
        ("Thursday Service Day", "2026-11-12T09:00:00-05:00", "2026-11-12T12:00:00-05:00")
    ]
    assert result.events[0]["address"] is None  # sent to those who sign up
    got = reasons(result)
    assert got["Trained Crew Day"].startswith("not under a heading this source takes")
    assert (
        got["Crew Leader Recruitment Party"] == "title matches the source's drop rule: Recruitment"
    )
    assert got["Date To Be Announced"] == "date or year could not be read"  # no year: never guessed
    assert [d.reason for d in result.dropped].count("the same event twice on this page") == 1


def test_accordion_reports_a_changed_layout():
    with pytest.raises(SourceError, match="layout may have changed"):
        accordion_event_list.parse(
            "<main>No sections</main>", entry("accordion_event_list"), READ_AT
        )


# -- bl_events ------------------------------------------------------------------


def card(title: str, day: str, times: str, href: str, desc: str = "", place: str = "") -> str:
    return f"""<article class="the-event"><div class="date-desc">{day}</div>
    <div class="time-desc">{times}</div><h2><a href="{href}">{title}</a></h2>
    <div class="desc"><p>{desc}</p></div><span class="the-location">{place}</span></article>"""


BL = "https://parks.example.org/bl_events/"
BL_PAGE = "".join(
    [
        card(
            "Planting",
            "Saturday, November 7",
            "9:00 am - 12:00 pm",
            f"{BL}planting/?eDate=20261107&date=1",
            place="Creek Park",
        ),
        card(
            "We Walk PHL: Creek Loop",
            "Sunday, November 8",
            "10:00 am - 11:00 am",
            f"{BL}walk/?eDate=20261108",
        ),
        card(
            "Fall Weekend",
            "Friday, November 13 - Sunday, November 15",
            "",
            f"{BL}fall/?eDate=20261113",
        ),
        card(
            "Gala Cleanup",
            "Saturday, November 14",
            "9:00 am - 12:00 pm",
            f"{BL}gala/?eDate=20261114",
            desc="Tickets are $25 per person.",
        ),
        card("No Year", "Saturday, November 21", "9:00 am - 12:00 pm", f"{BL}noyear/"),
        card(
            "Wrong Day", "Saturday, November 21", "9:00 am - 12:00 pm", f"{BL}wrong/?eDate=20261122"
        ),
        card(
            "Evening Cleanup",
            "Wednesday, November 18",
            "5:30 - 7:00 pm",
            f"{BL}evening/?eDate=20261118",
        ),
    ]
)


def test_bl_events_keeps_shifts_and_drops_the_rest():
    source = entry("bl_events", drop_titles=["We Walk PHL"])
    result = bl_events.parse_with_report(BL_PAGE, source, READ_AT)
    events = {e["title"]: e for e in result.events}
    assert set(events) == {"Planting", "Evening Cleanup"}
    assert events["Planting"]["start"] == "2026-11-07T09:00:00-05:00"
    assert events["Planting"]["address"] == "Creek Park"
    assert events["Planting"]["source_url"] == f"{BL}planting/?eDate=20261107"
    assert events["Evening Cleanup"]["start"] == "2026-11-18T17:30:00-05:00"
    got = reasons(result)
    assert got["We Walk PHL: Creek Loop"] == "title matches the source's drop rule: We Walk PHL"
    assert got["Fall Weekend"].startswith("runs over several days")
    assert got["Gala Cleanup"].startswith("asks for a price or fee")
    assert got["No Year"] == "no year in the event link (eDate)"
    assert got["Wrong Day"] == "the date on the card and in the link do not agree"


def test_bl_events_reports_a_changed_layout():
    with pytest.raises(SourceError, match="layout may have changed"):
        bl_events.parse("<main>Nothing</main>", entry("bl_events"), READ_AT)


# -- apostrophe_events ----------------------------------------------------------


def preview(title: str, href: str, *lines: str) -> str:
    h5 = "".join(f'<h5 class="apostrophe-event-date">{x}</h5>' for x in lines)
    return f"""<div class="apostrophe-event-preview c-slat"><a href="{href}"
    class="apostrophe-event-title">{title}</a>{h5}
    <div class="apostrophe-event-body">Call our coordinator for details.</div></div>"""


EV = "https://parks.example.org/events/"
AP_PAGE = (
    '<div class="c-upcoming-events">'
    + "".join(
        [
            preview(
                "Park Stewardship",
                f"{EV}park-stewardship11-2026",
                "November 7th",
                "9:00am – 10:00am",
            ),
            preview(
                "Rail Park Clean Up",
                f"{EV}rail-park-11-18",
                "1300 Noble Street",
                "November 18th",
                "5:30 - 7:00 pm",
            ),
            preview(
                "Second Saturday",
                f"{EV}second-saturday-01-09",
                "Woods",
                "January 9th",
                "10:00am – 12:00pm",
            ),
            preview("Old Slug", f"{EV}old-slug-12-12-25", "December 12th", "10:00am – 12:00pm"),
            preview(
                "We Walk PHL: Fall Stroll",
                f"{EV}we-walk-11-21",
                "November 21st",
                "10:00am – 11:00am",
            ),
            preview(
                "Fall Weekend",
                f"{EV}fall-weekend",
                "Parks",
                "November 13th – November 15th",
                "All Day",
            ),
            preview(
                "Park Stewardship",
                f"{EV}park-stewardship11-2026",
                "November 7th",
                "9:00am – 10:00am",
            ),
        ]
    )
    + "</div>"
)


def test_apostrophe_events_reads_upcoming_cards():
    source = entry("apostrophe_events", drop_titles=["We Walk PHL"])
    result = apostrophe_events.parse_with_report(AP_PAGE, source, READ_AT)
    events = {e["title"]: e for e in result.events}
    assert set(events) == {"Park Stewardship", "Rail Park Clean Up", "Second Saturday"}
    assert events["Park Stewardship"]["start"] == "2026-11-07T09:00:00-05:00"
    assert events["Rail Park Clean Up"]["start"] == "2026-11-18T17:30:00-05:00"  # evening shift
    assert events["Rail Park Clean Up"]["address"] == "1300 Noble Street"
    assert events["Second Saturday"]["start"] == "2027-01-09T10:00:00-05:00"  # next January
    assert all(e["org_name"] == "Example Parks" for e in result.events)
    got = reasons(result)
    assert got["Old Slug"].startswith("year unclear")  # address says 2025; upcoming says 2026
    assert got["We Walk PHL: Fall Stroll"] == "title matches the source's drop rule: We Walk PHL"
    assert got["Fall Weekend"].startswith("runs over several days or all day")
    assert [d.reason for d in result.dropped].count("the same event twice on this page") == 1


def test_apostrophe_year_rules():
    read = datetime(2026, 11, 5, 12, tzinfo=UTC)
    assert apostrophe_events.upcoming_year(11, 4, read) == 2026  # the day before: still listed
    assert apostrophe_events.upcoming_year(11, 3, read) == 2027
    assert apostrophe_events.upcoming_year(2, 29, read) is None  # no Feb 29 in the window
    assert apostrophe_events.slug_year(f"{EV}x-11-7-26", 11, 7) == 2026
    assert apostrophe_events.slug_year(f"{EV}x11-2026", 11, 7) == 2026
    assert apostrophe_events.slug_year(f"{EV}x-12-12", 12, 12) is None


def test_apostrophe_reports_a_changed_layout():
    with pytest.raises(SourceError, match="layout may have changed"):
        apostrophe_events.parse("<main>Nothing</main>", entry("apostrophe_events"), READ_AT)


def test_drop_titles_must_be_a_list_of_words():
    with pytest.raises(SourceError, match="drop_titles"):
        bl_events.parse(BL_PAGE, entry("bl_events", drop_titles="We Walk"), READ_AT)


# -- mec_events -----------------------------------------------------------------


MEC = "https://orchards.example.org/events-new/"
JSON_LD = (
    '<script type="application/ld+json">{"@type": "Event", "name": "Orchard Work Day", '
    '"startDate": "2026-11-10T05:00:00-05:00", "offers": {"price": "0"}}</script>'
)


def mec_card(
    title, href, day, start, end, *, group="202611", label="", desc="", organizer="A. Person"
):
    label_html = (
        f'<span class="mec-event-title-soldout"><span class="soldout">{label}</span></span>'
        if label
        else ""
    )
    return f"""<article class="mec-event-article mec-toggle-{group}-1">
    <h3 class="mec-event-title"><a href="{href}">{title}</a> {label_html}</h3>
    <div class="mec-event-description">{desc}</div>
    <span class="mec-start-date-label">{day}</span>
    <span class="mec-start-time">{start}</span> - <span class="mec-end-time">{end}</span>
    <div class="mec-venue-details"><span>Learning Orchard</span>
      <address class="mec-event-address"><span>4000 Woodland Ave, Philadelphia, PA 19104</span></address></div>
    <div class="mec-shortcode-organizers"><ul><li class="mec-organizer-item"><span>{organizer}</span></li></ul></div>
    <a href="{href}?method=mec-booking-modal">Register Now</a></article>"""


MEC_PAGE = (
    '<div class="mec-wrap"><div class="mec-event-list-standard">'
    '<div class="mec-month-divider"><h5>November 2026</h5></div>'
    + JSON_LD
    + mec_card("Orchard Work Day", f"{MEC}work-day/", "Tue, Nov 10", "10:00 am", "12:30 pm")
    + mec_card(
        "Fall Planting", f"{MEC}planting/", "Sat, Nov 14", "9:30 am", "12:00 pm", label="Sold Out"
    )
    + mec_card(
        "Harvest Day",
        f"{MEC}harvest/",
        "Sat, Nov 14",
        "1:00 pm",
        "3:00 pm",
        label="Last Few Tickets",
    )
    + mec_card("Grafting Workshop Work Day", f"{MEC}workshop/", "Sun, Nov 15", "1:00 pm", "3:00 pm")
    + mec_card("Open Orchard Hours: November", f"{MEC}open/", "Sat, Nov 21", "10:00 am", "1:00 pm")
    + mec_card(
        "Pruning Work Day",
        f"{MEC}paid/",
        "Sun, Nov 22",
        "10:00 am",
        "12:00 pm",
        desc="Tickets $15.",
    )
    + mec_card("Members Picnic", f"{MEC}picnic/", "Sun, Nov 22", "1:00 pm", "3:00 pm")
    + mec_card("Winter Work Day", f"{MEC}winter/", "Tue, Dec 1", "10:00 am", "12:00 pm")
    + "</div></div>"
)


def mec_source(**extra):
    return entry(
        "mec_events",
        require_titles=["work day", "workday", "planting", "harvest"],
        drop_titles=["Open Orchard Hours", "Workshop"],
        **extra,
    )


def test_mec_reads_the_visible_list_only():
    result = mec_events.parse_with_report(MEC_PAGE, mec_source(), READ_AT)
    events = {e["title"]: e for e in result.events}
    assert set(events) == {"Orchard Work Day", "Fall Planting", "Harvest Day"}
    # The visible 10:00 am, never the schema.org data's 05:00.
    assert events["Orchard Work Day"]["start"] == "2026-11-10T10:00:00-05:00"
    assert events["Orchard Work Day"]["end"] == "2026-11-10T12:30:00-05:00"
    assert events["Orchard Work Day"]["address"] == (
        "Learning Orchard, 4000 Woodland Ave, Philadelphia, PA 19104"
    )
    assert events["Orchard Work Day"]["signup_url"] == f"{MEC}work-day/"  # its own page
    assert events["Fall Planting"]["full"] is True  # "Sold Out"
    assert events["Harvest Day"]["full"] is False  # "Last Few Tickets" is not a price or full
    assert "A. Person" not in str(result.events) + str(result.dropped)  # never the contact
    got = reasons(result)
    assert got["Grafting Workshop Work Day"] == "title matches the source's drop rule: Workshop"
    assert got["Open Orchard Hours: November"].startswith("title matches the source's drop rule")
    assert got["Members Picnic"] == "title has none of the words this source requires"
    assert got["Pruning Work Day"].startswith("shows a price")
    assert got["Winter Work Day"] == "the year could not be read from the month heading"


def test_mec_price_element_drops_the_event():
    priced = MEC_PAGE.replace(
        '<div class="mec-event-description"></div>',
        '<div class="mec-event-description"></div><div class="mec-event-cost">$10</div>',
        1,
    )
    result = mec_events.parse_with_report(priced, mec_source(), READ_AT)
    assert reasons(result)["Orchard Work Day"].startswith("shows a price")


def test_mec_reports_a_changed_layout():
    with pytest.raises(SourceError, match="layout may have changed"):
        mec_events.parse("<main>Nothing</main>", mec_source(), READ_AT)


def test_require_titles_must_be_a_list_of_words():
    with pytest.raises(SourceError, match="require_titles"):
        mec_events.parse(MEC_PAGE, entry("mec_events", require_titles="work day"), READ_AT)
