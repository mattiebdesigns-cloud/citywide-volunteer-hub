// Tests for the site's logic (PROJECT.md 2, 4, 8). Run from site/: npm test
// Node runs TypeScript directly (Node 22.18+ / 24).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { addDays, localParts, timeOfDay } from "../src/lib/time.ts";
import { checkSettings, liveAreas, prepareListings, spotsStatus, usedIds } from "../src/lib/prepare.ts";
import { EMPTY_FILTERS, activeCount, matches, type CardFacts } from "../src/lib/filter-logic.ts";
import { buildIcs, escapeText, foldLine } from "../src/lib/ics.ts";
import { pruneSaved } from "../src/lib/saved.ts";
import type { EventsFile, SiteSettings } from "../src/lib/types.ts";

const settings: SiteSettings = JSON.parse(readFileSync(new URL("../settings.example.json", import.meta.url), "utf8"));
const sample: EventsFile = JSON.parse(
  readFileSync(new URL("../../docs/examples/events.sample.json", import.meta.url), "utf8"),
);
const hours = settings.time_of_day;
const before = new Date("2026-10-01T00:00:00Z");

test("time of day uses the city's own hours", () => {
  assert.equal(timeOfDay(4 * 60 + 59, hours), "overnight");
  assert.equal(timeOfDay(5 * 60, hours), "morning");
  assert.equal(timeOfDay(12 * 60, hours), "afternoon");
  assert.equal(timeOfDay(17 * 60 + 30, hours), "evening");
  assert.equal(timeOfDay(22 * 60, hours), "overnight");
  assert.throws(() => timeOfDay(0, { ...hours, evening: "11:00" }));
});

test("local date is in the city's time zone, not UTC", () => {
  // 02:30 UTC on Oct 21 is 22:30 on Oct 20 in New York.
  const p = localParts("2026-10-21T02:30:00Z", "America/New_York");
  assert.equal(p.date, "2026-10-20");
  assert.equal(p.weekday, 2);
  assert.equal(p.minutes, 22 * 60 + 30);
  assert.equal(addDays("2026-12-31", 1), "2027-01-01");
});

test("sample settings pass the settings check; a broken one fails plainly", () => {
  checkSettings(settings, "example");
  const broken = structuredClone(settings) as unknown as Record<string, any>;
  delete broken.features;
  assert.throws(() => checkSettings(broken as SiteSettings, "broken"), /features.campaigns/);
});

test("listings are sorted soonest first and past ones are dropped", () => {
  const all = prepareListings(sample, settings, { now: before });
  assert.equal(all.length, sample.events.length);
  assert.deepEqual(
    all.map((e) => e.start),
    [...all.map((e) => e.start)].sort((a, b) => Date.parse(a) - Date.parse(b)),
  );
  const later = prepareListings(sample, settings, { now: new Date("2026-10-25T00:00:00Z") });
  assert.ok(later.every((e) => Date.parse(e.end ?? e.start) >= Date.parse("2026-10-25T00:00:00Z")));
});

test("features.campaigns off leaves no campaign listing in the build (PROJECT.md 8)", () => {
  const withCampaign: EventsFile = {
    ...sample,
    events: [...sample.events, { ...sample.events[0], id: "campaign1", type: "campaign" }],
  };
  const on = prepareListings(withCampaign, settings, { now: before });
  assert.ok(on.some((e) => e.type === "campaign"));
  const off = prepareListings(withCampaign, { ...settings, features: { campaigns: false } }, { now: before });
  assert.ok(off.every((e) => e.type !== "campaign"));
});

test("protest_action is always treated as sensitive", () => {
  const file: EventsFile = { ...sample, events: [{ ...sample.events[0], type: "protest_action", sensitive: false }] };
  assert.equal(prepareListings(file, settings, { now: before })[0].sensitive, true);
});

test("only live areas go in the area filter (PROJECT.md 4)", () => {
  assert.deepEqual(liveAreas(settings), ["philadelphia"]);
  assert.deepEqual(usedIds(["a", "b", "c"], ["c", null, "a", "a"]), ["a", "c"]);
});

test("open spots: full, count, or nothing; never a guess (decisions 0008, 0011)", () => {
  const built = new Date("2026-10-13T12:00:00Z");
  const base = { last_seen_at: "2026-10-13T05:00:00-04:00" };
  assert.deepEqual(spotsStatus({ ...base, full: true, spots_left: null }, built), { kind: "full" });
  assert.deepEqual(spotsStatus({ ...base, full: false, spots_left: 0 }, built), { kind: "full" });
  assert.deepEqual(spotsStatus({ ...base, full: false, spots_left: 6 }, built), { kind: "spots", count: 6, withinWeek: true });
  assert.equal(spotsStatus({ ...base, full: false, spots_left: 6 }, new Date("2026-10-20T00:00:00Z"))?.kind, "spots");
  assert.equal(
    (spotsStatus({ ...base, full: false, spots_left: 6 }, new Date("2026-10-20T00:00:00Z")) as { withinWeek: boolean }).withinWeek,
    false,
  );
  // Read on Monday, built on Friday: still within the week, so the weekday is shown.
  assert.equal(
    (spotsStatus({ ...base, full: false, spots_left: 6 }, new Date("2026-10-17T12:00:00Z")) as { withinWeek: boolean }).withinWeek,
    true,
  );
  assert.equal(spotsStatus({ ...base, full: false, spots_left: null }, built), null);
});

const card: CardFacts = {
  id: "x",
  date: "2026-10-24",
  weekday: 6,
  time: "morning",
  area: "philadelphia",
  cause: "food",
  type: "service",
  join: "drop_in",
  training: "false",
  spanish: "unknown",
  host: "business-led",
  faith: "",
  activities: ["outdoors", "physical"],
};
const today = "2026-10-20"; // a Tuesday
const none = new Set<string>();

test("day filters", () => {
  const f = (day: string, date = "") => matches(card, { ...EMPTY_FILTERS, day, date }, today, none);
  assert.equal(f(""), true);
  assert.equal(f("today"), false);
  assert.equal(f("this_week"), true);
  assert.equal(f("this_weekend"), true);
  assert.equal(f("pick_date", "2026-10-24"), true);
  assert.equal(f("pick_date", "2026-10-25"), false);
  assert.equal(matches({ ...card, date: "2026-10-21", weekday: 3 }, { ...EMPTY_FILTERS, day: "tomorrow" }, today, none), true);
});

test("show only and hide tags, unknown never counts as a match", () => {
  const f = (state: Partial<typeof EMPTY_FILTERS>) => matches(card, { ...EMPTY_FILTERS, ...state }, today, none);
  assert.equal(f({ host: "hide:business-led" }), false);
  assert.equal(f({ host: "only:business-led" }), true);
  assert.equal(f({ host: "only:nonprofit" }), false);
  assert.equal(f({ activity: "hide:indoors" }), true);
  assert.equal(f({ activity: "only:outdoors" }), true);
  assert.equal(f({ no_training: true }), true);
  assert.equal(matches({ ...card, training: "" }, { ...EMPTY_FILTERS, no_training: true }, today, none), false);
  assert.equal(f({ spanish: true }), false);
  assert.equal(f({ saved: true }), false);
  assert.equal(matches(card, { ...EMPTY_FILTERS, saved: true }, today, new Set(["x"])), true);
  assert.equal(activeCount({ ...EMPTY_FILTERS, day: "pick_date" }), 0);
  assert.equal(activeCount({ ...EMPTY_FILTERS, day: "today", spanish: true }), 2);
});

test("calendar file follows RFC 5545", () => {
  assert.equal(escapeText("a,b;c\\d\ne"), "a\\,b\\;c\\\\d\\ne");
  const long = "DESCRIPTION:" + "é".repeat(80);
  for (const line of foldLine(long).split("\r\n")) assert.ok(new TextEncoder().encode(line).length <= 75);
  const ics = buildIcs(sample.events[0], { location: "100 Example Street", description: "Hello" });
  assert.match(ics, /^BEGIN:VCALENDAR\r\n/);
  assert.match(ics, /DTSTART:20261020T220000Z\r\n/);
  assert.match(ics, /DTEND:20261021T003000Z\r\n/);
  assert.match(ics, /END:VCALENDAR\r\n$/);
});

test("saved shifts are cleared once over or no longer listed (owner, Q32)", () => {
  const now = Date.parse("2026-10-21T12:00:00Z");
  const live = new Map([
    ["future", Date.parse("2026-10-24T13:00:00Z")],
    ["ended", Date.parse("2026-10-20T22:30:00Z")],
    ["ends-now", now],
  ]);
  const kept = pruneSaved(["future", "ended", "gone", "ends-now"], live, now);
  assert.deepEqual([...kept].sort(), ["ends-now", "future"]);
  assert.equal(pruneSaved([], live, now).size, 0);
});
