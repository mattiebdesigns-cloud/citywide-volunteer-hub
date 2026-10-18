// The words shown for one listing, in one language. Every word comes from the
// translation files (PROJECT.md 5); organization text goes in as placeholders.
import type { Translator } from "../i18n/index.ts";
import { spotsStatus } from "./prepare.ts";
import type { PreparedListing } from "./types.ts";

export function timeText(tr: Translator, e: PreparedListing): string {
  const start = tr.formatTime(e.start);
  return e.end ? tr.t("listing.time_range", { start, end: tr.formatTime(e.end) }) : tr.t("listing.starts_at", { start });
}

/** "Tuesday, October 20, 2026, 6:00 PM to 8:30 PM" */
export function whenText(tr: Translator, e: PreparedListing): string {
  return tr.t("listing.date_time", { date: tr.formatDate(e.start), time: timeText(tr, e) });
}

/** Neighborhood or town, else the area's name, else nothing. */
export function placeText(tr: Translator, e: PreparedListing): string {
  return e.neighborhood_or_town ?? tr.areaName(e.area);
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
