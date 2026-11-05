// The words shown for one listing, in one language. Every word comes from the
// translation files (PROJECT.md 5); organization text goes in as placeholders.
import type { Translator } from "../i18n/index.ts";
import { spotsStatus } from "./prepare.ts";
import type { PreparedListing, SiteSettings } from "./types.ts";

export function timeText(tr: Translator, e: PreparedListing): string {
  const start = tr.formatTime(e.start);
  return e.end ? tr.t("listing.time_range", { start, end: tr.formatTime(e.end) }) : tr.t("listing.starts_at", { start });
}

/** "Tuesday, October 20, 2026, 6:00 PM to 8:30 PM" */
export function whenText(tr: Translator, e: PreparedListing): string {
  return tr.t("listing.date_time", { date: tr.formatDate(e.start), time: timeText(tr, e) });
}

/**
 * A section's name in this language, from `sections` in the settings file
 * (decision 0013), the same way area names work. Empty for null, an unknown
 * id, or settings with no `sections`, so the page can leave it out.
 */
export function sectionName(
  tr: Translator,
  settings: Pick<SiteSettings, "sections">,
  id: string | null | undefined,
): string {
  const section = id ? settings.sections?.find((s) => s.id === id) : undefined;
  return section ? tr.setting(section.name) : "";
}

/** The place fields shared by listings and flexible opportunities. */
type Place = Pick<PreparedListing, "section" | "neighborhood_or_town" | "area">;

/** Section and neighborhood, when both are known and differ; otherwise null. */
function placePair(tr: Translator, e: Place, settings: Pick<SiteSettings, "sections">) {
  const section = sectionName(tr, settings, e.section);
  const neighborhood = e.neighborhood_or_town?.trim() ?? "";
  return section && neighborhood && !sameName(section, neighborhood) ? { section, neighborhood } : null;
}

/**
 * The card's place line (decision 0013): "River Wards · Kensington"
 * (listing.place_pair). Only one of section and neighborhood known: that one.
 * Neither: the area's name, as before. The neighborhood is a proper name and
 * is never translated.
 */
export function placeText(tr: Translator, e: Place, settings: Pick<SiteSettings, "sections">): string {
  const pair = placePair(tr, e, settings);
  if (pair) return tr.t("listing.place_pair", pair);
  return sectionName(tr, settings, e.section) || e.neighborhood_or_town?.trim() || tr.areaName(e.area);
}

/**
 * What a screen reader says for the place line when it is a pair: "River
 * Wards, Kensington" (listing.place_pair_spoken), since the dot between them
 * is read out or skipped. Empty when the line is one name, which reads fine.
 */
export function placeSpoken(tr: Translator, e: Place, settings: Pick<SiteSettings, "sections">): string {
  const pair = placePair(tr, e, settings);
  return pair ? tr.t("listing.place_pair_spoken", pair) : "";
}

/** The detail page's place lines: address, neighborhood, section, area; empties and repeats left out. */
export function whereLines(tr: Translator, e: PreparedListing, settings: Pick<SiteSettings, "sections">): string[] {
  const lines: string[] = [];
  for (const line of [e.address, e.neighborhood_or_town, sectionName(tr, settings, e.section), tr.areaName(e.area)]) {
    const text = line?.trim();
    if (text && !lines.some((l) => sameName(l, text))) lines.push(text);
  }
  return lines;
}

function sameName(a: string, b: string): boolean {
  return a.localeCompare(b, undefined, { sensitivity: "base" }) === 0;
}

export function joinLabel(tr: Translator, e: PreparedListing): string {
  return tr.t(`filters.join.${e.join_method}`);
}

/** Listing type words, except for plain service shifts, which need no label. */
export function typeLabel(tr: Translator, e: PreparedListing): string | undefined {
  return e.type === "service" ? undefined : tr.t(`filters.type.${e.type}`);
}

export function businessLabel(tr: Translator, e: PreparedListing): string | undefined {
  return e.host_type === "business-led" ? tr.listName("host_types", "business-led") || undefined : undefined;
}

/** "Full", "6 spots left as of Monday", or nothing (decisions 0008, 0011). */
export function spotsLabel(
  tr: Translator,
  e: PreparedListing,
  builtAt: Date,
): { label: string; full?: boolean } | undefined {
  const status = spotsStatus(e, builtAt);
  if (!status) return undefined;
  if (status.kind === "full") return { label: tr.t("listing.full"), full: true };
  return status.withinWeek
    ? { label: tr.plural("listing.spots_left", status.count, { day: tr.formatWeekday(e.last_seen_at) }) }
    : { label: tr.plural("listing.spots_left_on", status.count, { date: tr.formatDate(e.last_seen_at) }) };
}

/**
 * Splits a translated sentence around one placeholder, so the page can put
 * the value in its own element, e.g. an organization's name marked with its
 * own language: "Hosted by {org}" gives ["Hosted by ", ""]. If the
 * placeholder is missing, the value goes at the end.
 */
export function splitAround(text: string, name: string): [string, string] {
  const mark = `{${name}}`;
  const at = text.indexOf(mark);
  return at === -1 ? [`${text} `, ""] : [text.slice(0, at), text.slice(at + mark.length)];
}
