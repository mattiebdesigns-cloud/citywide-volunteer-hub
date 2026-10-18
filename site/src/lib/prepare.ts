// Turns the raw events file into the listings the site shows (PROJECT.md 2, 4, 8).
// Pure functions, so they can be tested without a build.
import type { EventsFile, Listing, PreparedListing, SiteSettings } from "./types.ts";
import { localParts, timeOfDay } from "./time.ts";

export interface PrepareOptions {
  /** Listings that are over before this moment are left out. */
  now: Date;
}

/** Checks the settings fields the site needs, with plain error messages. */
export function checkSettings(settings: SiteSettings, source: string): void {
  const problems: string[] = [];
  const s = settings?.site;
  if (!s) problems.push("site is missing");
  else {
    if (!s.name) problems.push("site.name is missing");
    if (!s.region) problems.push("site.region is missing");
    if (!s.timezone) problems.push("site.timezone is missing");
    else {
      try {
        new Intl.DateTimeFormat("en", { timeZone: s.timezone });
      } catch {
        problems.push(`site.timezone "${s.timezone}" is not a time zone name`);
      }
    }
    if (!s.contact_email || !String(s.contact_email).includes("@")) problems.push("site.contact_email is missing");
  }
  if (!settings?.languages?.default || !Array.isArray(settings?.languages?.available)) {
    problems.push("languages.default and languages.available are needed");
  }
  if (!Array.isArray(settings?.areas)) problems.push("areas is missing");
  if (!Array.isArray(settings?.causes)) problems.push("causes is missing");
  for (const name of ["morning", "afternoon", "evening", "overnight"] as const) {
    if (!settings?.time_of_day?.[name]) problems.push(`time_of_day.${name} is missing`);
  }
  if (typeof settings?.features?.campaigns !== "boolean") {
    problems.push("features.campaigns must be true or false");
  }
  if (problems.length) {
    throw new Error(`The settings file ${source} cannot be used:\n  - ${problems.join("\n  - ")}`);
  }
}

/** Checks the overall shape of the events file. The pipeline checks each listing against the schema. */
export function checkEventsFile(file: EventsFile, source: string): void {
  if (!file || typeof file.generated_at !== "string" || !Array.isArray(file.events)) {
    throw new Error(`The events file ${source} must have "generated_at" and an "events" list (docs/EVENT-FORMAT.md)`);
  }
  const seen = new Set<string>();
  for (const e of file.events) {
    if (!e?.id || !/^[A-Za-z0-9_-]+$/.test(e.id)) {
      throw new Error(`The events file ${source} has a listing with a missing or unusable id: ${JSON.stringify(e?.id)}`);
    }
    if (seen.has(e.id)) throw new Error(`The events file ${source} lists id ${e.id} twice`);
    seen.add(e.id);
    if (Number.isNaN(Date.parse(e.start))) throw new Error(`Listing ${e.id} has no usable start time`);
  }
}

/**
 * The listings to publish, soonest first.
 * - Campaign listings exist only when features.campaigns is on (PROJECT.md 8).
 * - Listings already over are left out.
 * - A listing marked protest_action is always treated as sensitive (8.1), whatever the file says.
 */
export function prepareListings(file: EventsFile, settings: SiteSettings, { now }: PrepareOptions): PreparedListing[] {
  const tz = settings.site.timezone;
  return file.events
    .filter((e) => settings.features.campaigns || e.type !== "campaign")
    .map((e): PreparedListing => {
      const start = localParts(e.start, tz);
      const end = e.end ? localParts(e.end, tz) : null;
      const overAt = Date.parse(e.end ?? e.start);
      return {
        ...normalise(e),
        localDate: start.date,
        weekday: start.weekday,
        timeOfDay: timeOfDay(start.minutes, settings.time_of_day),
        endsNextDay: end !== null && end.date > start.date,
        overAt,
      };
    })
    .filter((e) => e.overAt >= now.getTime())
    .sort((a, b) => Date.parse(a.start) - Date.parse(b.start) || a.id.localeCompare(b.id));
}

function normalise(e: Listing): Listing {
  const full = e.full === true;
  return {
    ...e,
    sensitive: e.sensitive === true || e.type === "protest_action",
    host_type: e.host_type ?? null,
    faith_tradition: e.faith_tradition ?? null,
    activity: Array.isArray(e.activity) && e.activity.length ? e.activity : null,
    full,
    spots_left: typeof e.spots_left === "number" ? e.spots_left : null,
    spots_total: typeof e.spots_total === "number" ? e.spots_total : null,
  };
}

/** Area ids shown in the area filter: only areas marked live in the settings (PROJECT.md 4). */
export function liveAreas(settings: SiteSettings): string[] {
  return settings.areas.filter((a) => a.live === true).map((a) => a.id);
}

/** Ids from a settings list that at least one listing uses, in the settings' order. */
export function usedIds(list: string[] | undefined, values: Iterable<string | null | undefined>): string[] {
  const used = new Set<string>();
  for (const v of values) if (v) used.add(v);
  return (list ?? []).filter((id) => used.has(id));
}

/**
 * Open spots (decision 0008). `withinWeek` is true when the count was read in
 * the six days before the build, so the weekday alone is clear ("as of
 * Monday"); older counts show the full date. Sources are read on set days,
 * not nightly (decision 0011), so the site never says "last night".
 */
export function spotsStatus(
  e: Pick<Listing, "full" | "spots_left" | "last_seen_at">,
  builtAt: Date,
): { kind: "full" } | { kind: "spots"; count: number; withinWeek: boolean } | null {
  // 0 spots left on the organization's page is shown the same way as "Full".
  if (e.full || e.spots_left === 0) return { kind: "full" };
  if (typeof e.spots_left === "number" && e.spots_left > 0) {
    const age = builtAt.getTime() - Date.parse(e.last_seen_at);
    return { kind: "spots", count: e.spots_left, withinWeek: age >= 0 && age < 6 * 24 * 60 * 60 * 1000 };
  }
  return null;
}
