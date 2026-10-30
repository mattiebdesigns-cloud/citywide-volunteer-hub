# Calendar site

The Phase 1 calendar: a static website built with Astro. It reads one events file and one city settings file at build time and writes plain HTML to `dist/`. There is no server and no database. Anyone can build it with the sample data in this repo, with no key and no private file.

## Build it

You need Node 22.12 or newer to build (Astro 6 requires it), and Node 22.18 or newer to run `npm test`, which runs TypeScript directly. Node 24 is recommended; `.nvmrc` names it.

```sh
cd site
npm ci                 # installs exactly what package-lock.json lists
npm run build          # writes dist/ using the sample listings and settings.example.json
```

Look at it on your own computer with `npm run preview`, then open the address it prints.

### Build inputs

All optional. Relative paths are read from the folder you run the command in.

| Setting | What it is | Default |
|---|---|---|
| `PV_EVENTS` | The events file (`docs/EVENT-FORMAT.md`) | `../docs/examples/events.sample.json` |
| `PV_SETTINGS` | The city settings, as JSON | `settings.example.json` |
| `PV_SITE_URL` | The site's public address, for full links and link previews (below) | none |
| `PV_TEST_BUILD` | `1` makes a test build (below) | off |

Example, with a city's own files:

```sh
PV_EVENTS=/path/to/events.json PV_SETTINGS=/path/to/settings.json PV_SITE_URL=https://example.org npm run build
```

A city keeps its settings in its own private place. If they are in YAML, convert them to JSON first; never commit a real settings file here (`settings.json` is ignored by git).

### Test builds

`npm run build:test` (or `PV_TEST_BUILD=1`) makes a build for trying things out:

- a "Test version" line at the top of every page;
- `noindex, nofollow` on every page;
- a `robots.txt` that lets in only Facebook's link-preview bot (`facebookexternalhit`) and asks every other crawler to stay out (decision 0014).

A normal build's `robots.txt` lets every crawler in.

### Link previews

When someone shares a link on Facebook or a similar site, the post shows a picture, a title and a short description (decision 0014). Every page carries these tags (`og:*` and `twitter:card`) in its own language. The home page uses the site's name and `og.description`. A listing page uses exactly the home page's preview; only `og:url` points at the listing. No listing's title, date, organization or picture ever goes into a preview (owner, Q38). The pictures are `public/og/en.png` and `public/og/es.png`, 1200 × 630 px.

**Set `PV_SITE_URL` for previews to show a picture.** Facebook needs a full web address for the picture and the page. Without `PV_SITE_URL`, the build leaves out `og:image` and `og:url`, and a shared link shows text only.

## Checks

```sh
npm test               # logic (time of day, filters, campaign switch, open spots, calendar file) and built pages (link previews, robots.txt, place line)
npm run check          # TypeScript and Astro type check
npm run check:licences # every npm package has an allowed licence (MIT, Apache-2.0, BSD, ISC, PSF-2.0, Python-2.0, BlueOak-1.0.0, CC0-1.0)
npm run check:strings  # after a build: any interface text missing from src/i18n/
```

## How it is put together

| Folder | What is in it | Who looks after it |
|---|---|---|
| `src/pages/` | Root page (sends people to their language), home page, listing pages, 404, robots.txt | calendar site |
| `src/layouts/`, `src/components/*.astro` | Page frame, header, language switch, filter panel | calendar site |
| `src/lib/` | Reading the inputs, time zones, filters, the calendar file, listing words | calendar site |
| `src/scripts/` | Browser code: filters, heart, share, add to calendar | calendar site |
| `src/components/ui/`, `src/styles/` | Look and feel: cards, buttons, pills, drawings, colours | design |
| `src/i18n/` | Every word, in English and Spanish | languages |

Rules the code follows:

- **Every word comes from `src/i18n/`.** Organization names and titles are shown as the organization wrote them, marked with their language.
- **Filters run in the browser.** There is no form to submit, so filter choices never reach a server. They are kept for the open tab only.
- **Saved shifts (the heart) stay on the device** (`localStorage`). Nothing is sent anywhere.
- **"Add to my calendar" is made in the browser** from text already in the page, so no request records who saved which shift.
- **Report a problem** opens the visitor's email app, addressed to `site.contact_email`. The subject names the listing's id, never its title.
- **Campaign listings exist only when `features.campaigns` is true.** With it false, no campaign listing, filter choice or label is in the build.
- **Areas appear in the area filter only when the settings mark them `live`**, and only when there are two or more.
- **Where a shift is (decision 0013).** A card shows the section and neighborhood, such as "River Wards · Kensington"; only one known shows that one; neither shows the area name. Section names come from `sections` in the settings, like area names; with no `sections`, none are shown. The listing page lists address, neighborhood, section and area, skipping empty or repeated ones.
- **Open spots** show only when the organization's page gave them: "Full", or "6 spots left as of last night". Nothing is estimated.
- **No outside scripts, fonts or images.** No image processing either: `vendor/no-sharp` stands in for Astro's optional image package, whose image library has a licence this project does not allow.
