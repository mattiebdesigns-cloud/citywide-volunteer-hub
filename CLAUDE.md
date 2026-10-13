# Citywide Volunteer Hub (PUBLIC repo: citywide-volunteer-hub)

Everything committed here is, or will be, visible to anyone. Treat every commit as published.

## Never commit here
- A list of sources, organizations or campaigns to scrape
- Any key, token, `.env` file or account name
- Any data about a person, including test fixtures copied from real sign-up pages
- Any file from the private repo's `config/`, `supabase/`, `support/`, `outreach/` or `web/` folders
- Any code for profiles, points, friends, teams or sensitive events

## What belongs here
- Scraper code that takes a source entry as input and returns events in the shared format
- The Phase 1 calendar website in `site/`: pages, styles, English and Spanish interface text, and a small sample `events.json` so anyone can build it
- The event format (`docs/EVENT-FORMAT.md`, and its JSON Schema)
- Recorded fixtures of public calendar pages, with any personal names removed
- Tests

## Rules
- Permissive dependencies only (MIT, Apache-2.0, BSD, ISC, PSF-2.0).
- Nothing here is specific to Philadelphia. City name, region, areas and languages come from the settings file a city supplies; Philadelphia appears only as the example.
- Follow the four ground rules in README.md.
- The spec and the agent team live in the private repo. Work here is assigned by `pv-coordinator` there and reviewed by `pv-gate-scraping-licence` before every merge.
