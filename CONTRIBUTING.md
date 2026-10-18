# Helping with the Citywide Volunteer Hub

Thank you for looking. This is open code for a city's calendar of volunteer shifts. The first city is Philadelphia, where it runs as Philly Volunteers.

## Who runs it
The project is run by Cedar Water LLC, a small Philadelphia business owned by Mr. Bennett. It may later be handed to a nonprofit or to the city. The code and documentation in this repository are MIT licensed, so whatever happens to the project, the code you contribute here stays open for anyone to use. Recorded copies of public calendars under `tests/fixtures/` are the exception: they belong to their publishers and are kept only for testing (see `tests/fixtures/NOTICE.md`).

## What you can work on
- **Scrapers** (`pvscrapers/`): reading one more public volunteer calendar into the shared event format.
- **The calendar website** (`site/`): pages, filters, accessibility, phone layout, Spanish text.
- **Tests and fixtures.**

## What is not in this repository, and why
Source lists, keys, the database, and all code for profiles, points and attendance are kept private. The hub lists protests and other sensitive events, and the people who attend them must not be traceable through this project. Please do not ask for access to that data; nobody outside the owner and his appointed moderators has it.

## Ground rules
1. Never commit a key, a source list, or anything about a real person.
2. Follow the four scraper rules in README.md.
3. Permissive dependencies only (MIT, Apache-2.0, BSD, ISC, PSF-2.0, Python-2.0, BlueOak-1.0.0, CC0-1.0).
4. Open an issue before a large change, so work is not wasted.
5. Be kind. This is a volunteer project about volunteering.

## Bringing it to your city
The code is MIT licensed: you may run your own hub without asking. You supply your own settings (city name, areas, languages) and your own list of sources, and you are responsible for your own users' data. If you do start one, open an issue to say hello; shared scrapers for the common sign-up platforms help every city.

## How to start
Build the site from the sample data in `site/` (instructions will be added there once the first version exists), or pick an issue marked "good first issue".
