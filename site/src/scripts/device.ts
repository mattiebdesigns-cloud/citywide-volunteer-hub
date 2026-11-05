// Things kept on the visitor's own device only, never sent anywhere
// (docs/briefs/phase1-home-page.md; PROJECT.md 2). If storage is blocked
// (private browsing), the page still works; the choice just is not kept.

import { pruneSaved } from "../lib/saved.ts";

const SAVED_KEY = "cvh.saved";
let pruned = false;

/** Listings in this build and when each is over, from the page (layouts/Base.astro). */
function liveListings(): Map<string, number> | null {
  const el = document.getElementById("live-listings");
  if (!el?.textContent) return null;
  try {
    return new Map(JSON.parse(el.textContent) as Array<[string, number]>);
  } catch {
    return null;
  }
}

/**
 * Removes saved shifts that are over or no longer listed (owner, Q32).
 * Runs once per page load, before anything reads the saved list.
 */
export function pruneSavedNow(): void {
  if (pruned) return;
  pruned = true;
  const live = liveListings();
  if (!live) return; // a page without the list never clears anything by mistake
  const before = readSavedRaw();
  const after = pruneSaved(before, live, Date.now());
  if (after.size !== before.size) writeSaved(after);
}
const FILTERS_KEY = "cvh.filters";
/** Filters on the Flexible page are kept apart, so a day filter never empties it. */
export const FLEXIBLE_FILTERS_KEY = "cvh.filters.flexible";

export function readSaved(): Set<string> {
  pruneSavedNow();
  return readSavedRaw();
}

function readSavedRaw(): Set<string> {
  try {
    const raw = localStorage.getItem(SAVED_KEY);
    const list: unknown = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(list) ? list.filter((x): x is string => typeof x === "string") : []);
  } catch {
    return new Set();
  }
}

export function writeSaved(ids: Set<string>): void {
  try {
    localStorage.setItem(SAVED_KEY, JSON.stringify([...ids]));
  } catch {
    // storage blocked
  }
}

export function readFilters<T extends object>(fallback: T, key = FILTERS_KEY): T {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? { ...fallback, ...JSON.parse(raw) } : { ...fallback };
  } catch {
    return { ...fallback };
  }
}

export function writeFilters(state: object, key = FILTERS_KEY): void {
  try {
    sessionStorage.setItem(key, JSON.stringify(state));
  } catch {
    // storage blocked
  }
}
