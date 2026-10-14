"""Citywide Volunteer Hub scrapers.

Each scraper turns one public volunteer calendar into listings in the shared
event format (docs/EVENT-FORMAT.md). A scraper never holds a list of sources:
the city running the hub passes in one source entry at a time from its own
private settings.

Every scraper has two separate steps:

- fetch: `pvscrapers.fetch.Fetcher` downloads the source's page politely
  (robots.txt first, a named bot with a contact address, one request at a
  time, the site's crawl delay);
- parse: `parse(page_text, source, fetched_at)` turns the downloaded text into
  listings. It never touches the network, so it can be tested offline against
  a recorded copy of the page.
"""

__version__ = "0.1.0"
