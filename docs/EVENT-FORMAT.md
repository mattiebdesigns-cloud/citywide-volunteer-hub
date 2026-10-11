# Shared event format (draft)

One JSON object per listing. The Schema builder turns this into a JSON Schema and keeps this page in step with it.

| Field | Type | Notes |
|---|---|---|
| id | string | Stable across runs: hash of source_id + source's own event id |
| org_name | string | As the organization writes it |
| title | string | |
| start, end | ISO 8601 with offset | end may be null |
| address | string or null | |
| area | string | Supplied by the source entry |
| neighborhood_or_town | string or null | |
| cause | string or null | |
| type | service, training, campaign, protest_action | |
| sensitive | boolean | When unsure, true |
| signup_url | URL | The organization's own page |
| join_method | drop_in, signup, application, unknown | What a volunteer must do before turning up. Never guess: unknown is valid |
| min_age | integer or null | |
| listing_language | BCP 47 tag | Language the organization wrote it in |
| spanish_spoken | true, false, unknown | |
| training_required | boolean or null | |
| clearances_required | boolean or null | |
| group_friendly | boolean or null | |
| recurring | boolean | |
| recurrence_rule | iCalendar RRULE string or null | Set when the source or the poster gives a schedule, for example the third Thursday of each month |
| source_url | URL | Page the facts came from |
| source_id | string | Matches the source entry |
| last_seen_at | ISO 8601 | Set by the pipeline |

Scrapers never output names of attendees, counts by name, or sign-up lists.
