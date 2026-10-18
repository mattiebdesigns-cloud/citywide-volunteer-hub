# Shared event format

Every scraper turns a public volunteer calendar into listings in this format. The pipeline gathers them into one `events.json` file, and the calendar website reads that file.

The format is defined in two JSON Schema files (draft 2020-12). This page explains them in plain words. If this page and the schema disagree, the schema wins; report it as a bug.

| File | What it checks |
|---|---|
| `docs/event.schema.json` | One listing |
| `docs/events-file.schema.json` | The whole `events.json` file |
| `docs/examples/events.sample.json` | A small sample file of made-up events that passes both |

## The events.json file

```json
{ "generated_at": "2026-10-13T06:00:00-04:00", "events": [ ... ] }
```

- `generated_at`: when the pipeline wrote the file, with a UTC offset.
- `events`: every listing. Each `id` appears once. JSON Schema cannot check that, so the pipeline and tests do.

No other top-level fields are allowed.

## One listing

Every field in the first table must be present in every listing, even when its value is unknown. The tag fields and the open-spots fields in the later tables are optional. No other fields are allowed, so nothing extra (above all, nothing about people) can slip in.

| Field | Type | Notes |
|---|---|---|
| id | text | Stable across runs: a hash of `source_id` and the source's own event id |
| org_name | text | As the organization writes it |
| title | text | In the language the organization wrote it |
| start | date-time with offset | For example `2026-10-20T18:00:00-04:00` |
| end | date-time with offset, or null | null when the source gives no end time |
| address | text or null | |
| area | area id | An `id` from the city's settings file, for example `philadelphia` (an example city, as in the sample). Lowercase letters, digits and hyphens. Never a place name typed by the scraper |
| neighborhood_or_town | text or null | |
| cause | cause id, or null | An id from the city's cause list in its settings file, for example `food` or `parks-and-trees`. Same id rules as `area`. The listing-quality step maps the source's own words ("Hunger", "Food Access") to an id. null when unknown. Each city has its own list, so the schema does not fix the values |
| type | `service`, `training`, `campaign`, `protest_action` | |
| sensitive | true or false | Always true for `protest_action`. Also true for anything immigration-related or flagged sensitive. When unsure, true |
| photos_allowed | true or false | false when the listing says "no photos". Write true when the source says nothing |
| signup_url | web address | The organization's own page for joining. Sign-ups never happen on the hub |
| join_method | `drop_in`, `signup`, `application`, `unknown` | What a volunteer must do before turning up (see below) |
| min_age | whole number or null | Youngest age allowed |
| listing_language | language tag | BCP 47, for example `en` or `es`. The language the organization wrote the listing in |
| spanish_spoken | true, false or `"unknown"` | |
| training_required | true, false or null | |
| clearances_required | true, false or null | Background checks or clearances |
| group_friendly | true, false or null | |
| recurring | true or false | true when the shift repeats on a schedule |
| recurrence_rule | iCalendar RRULE or null | Without the `RRULE:` prefix, for example `FREQ=MONTHLY;BYDAY=3TH` (third Thursday each month). Set only when the source or poster gives the schedule. If it is set, `recurring` must be true |
| source_url | web address | The public page the facts came from |
| source_id | text | Matches the entry in the city's source list |
| last_seen_at | date-time with offset | When the pipeline last saw the listing on its source. Shown as "last checked" |

### Tags: host, faith tradition, activity (optional)

These three fields help people filter: "faith-hosted only", "outdoors", "with animals". They describe the host and the work, never the volunteers. Like `area` and `cause`, each value is an id from the city's settings file, and each city has its own lists, so the schema does not fix the values.

| Field | Type | Notes |
|---|---|---|
| host_type | host type id, or null | Who runs the shift, for example `nonprofit`, `government`, `faith-based`, `school-or-university`, `mutual-aid`, `business-led` |
| faith_tradition | faith tradition id, or null | Only when `host_type` is `faith-based`, for example `christian`, `jewish`, `interfaith`, `other`. null for every other host |
| activity | list of activity ids, or null | Any number, for example `["outdoors", "physical"]`. Each id once. null when unknown, never an empty list |

- Record them from the organization's own pages. Never guess: null is the only way to say "unknown".
- A `business-led` listing tells volunteers plainly that a business organized the day and may count the work and its impact as its own.
- Ids follow the same rules as `area` and `cause`: lowercase letters, digits and hyphens. Whether an id is on the city's list is checked against its settings file, not here.
- Older files may leave all three out. New output should always write them (null when unknown).

### Open spots (optional)

These three fields say whether a shift still has room. They are optional, so files written before they existed still pass.

| Field | Type | Notes |
|---|---|---|
| spots_left | whole number (0 or more) or null | Open spots, as the organization's own page shows them |
| spots_total | whole number (1 or more) or null | Total spots, as the organization's own page shows them |
| full | true or false, default false | true when the organization's own page says the shift is full |

- Take them only from the organization's own page, in the same read that sets `last_seen_at`. `last_seen_at` is the time of the count, so there is no separate "checked at" date. The site shows, for example, "6 spots left as of last night".
- Never estimate. If the page shows no count, write null. Do not fill in a "typical" number.
- Read the count only. Never read or store who signed up (scraper rule 5).
- A full listing stays on the calendar and shows "Full". It must not show open spots: when `full` is true, `spots_left` is 0 or null.
- Sensitive listings may show counts too, by the owner's decision (decision 0008): a kitchen shift for a protest group can still have a limit. Only the current count is kept, with no history of past counts.
- New scraper output should always write all three (`null`, `null`, `false` when the page shows nothing), so a listing has one way to say "no count". Leaving them out is allowed only so older files still pass.

### join_method

- `drop_in`: just show up.
- `signup`: reserve a place first; no reply needed.
- `application`: apply and wait for the organization to answer.
- `unknown`: the source does not say. The site shows "check with the organizer".

## When a fact is unknown: never guess

If the source does not say, record that it does not say. Each field has exactly one way to do this:

- `join_method` and `spanish_spoken` use the text `"unknown"`, because the site shows those two to visitors as "unknown" or "check with the organizer". They are never null.
- Every other field that can be unknown uses `null`: `end`, `address`, `neighborhood_or_town`, `cause`, `host_type`, `faith_tradition`, `activity`, `min_age`, `training_required`, `clearances_required`, `group_friendly`, `recurrence_rule`.
- `photos_allowed` is the one field with a default: true, unless the listing says "no photos".
- `sensitive` has no unknown: when unsure, write true.
- `spots_left` and `spots_total` use `null` when the page shows no count; `full` is false unless the page says full. All three may be left out of older files.

## Rules the schema checks

- A `protest_action` listing must have `sensitive: true`.
- A listing with a `recurrence_rule` must have `recurring: true`.
- A listing with `full: true` must have `spots_left` of 0 or null.
- Dates must include a UTC offset (`Z` or `-04:00`).
- `area`, and `cause`, `host_type`, `faith_tradition` and each `activity` when not null, must look like an id: lowercase letters, digits and hyphens. Whether it is on the city's lists is checked against the city's settings file, not here.
- `activity`, when not null, lists at least one id and no id twice.

## Nothing city-specific

The format names no city. Area ids, cause ids, host type, faith tradition and activity ids, the region name and languages come from the settings file each city supplies. Philadelphia appears only as the example: in the sample file and in example values on this page.

## Validating a file

Load both schema files into your validator. The file schema refers to the listing schema by its id, `urn:citywide-volunteer-hub:schema:event`. Turn on format checking so dates and web addresses are checked too.

## What a listing never holds

Scrapers never output names of attendees, counts by name, or sign-up lists. The open-spots fields hold only the numbers the organization itself shows to the public. They store facts and a link back, not the organization's full description or images.
