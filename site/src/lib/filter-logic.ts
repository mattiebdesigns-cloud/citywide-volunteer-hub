// Which listings match the visitor's filters (PROJECT.md 2). Runs in the
// browser only. Pure, so it can be tested without a page.
import { addDays } from "./time.ts";

/** What the page knows about one card, from its data attributes. */
export interface CardFacts {
  id: string;
  /** Local start date YYYY-MM-DD and weekday (0 = Sunday). */
  date: string;
  weekday: number;
  time: string;
  area: string;
  cause: string;
  type: string;
  join: string;
  /** "true", "false" or "" (unknown). */
  training: string;
  /** "true", "false" or "unknown". */
  spanish: string;
  host: string;
  faith: string;
  activities: string[];
}

export interface FilterState {
  day: string;
  date: string;
  time: string;
  area: string;
  cause: string;
  type: string;
  join: string;
  /** "", "only:<id>" or "hide:<id>" */
  host: string;
  faith: string;
  /** "", "only:<id>" or "hide:<id>" */
  activity: string;
  no_training: boolean;
  spanish: boolean;
  saved: boolean;
}

export const EMPTY_FILTERS: FilterState = {
  day: "",
  date: "",
  time: "",
  area: "",
  cause: "",
  type: "",
  join: "",
  host: "",
  faith: "",
  activity: "",
  no_training: false,
  spanish: false,
  saved: false,
};

/** How many filters are on, for the count next to the Filters button. */
export function activeCount(state: FilterState): number {
  let n = 0;
  for (const key of Object.keys(EMPTY_FILTERS) as Array<keyof FilterState>) {
    if (key === "date") continue; // part of the day filter
    if (key === "day" && state.day === "pick_date" && !state.date) continue;
    if (state[key]) n += 1;
  }
  return n;
}

function dayMatches(card: CardFacts, state: FilterState, today: string): boolean {
  switch (state.day) {
    case "":
      return true;
    case "today":
      return card.date === today;
    case "tomorrow":
      return card.date === addDays(today, 1);
    case "this_week": // today and the next six days
      return card.date >= today && card.date <= addDays(today, 6);
    case "this_weekend": // the coming Saturday and Sunday, or the rest of this one
      return card.date >= today && card.date <= addDays(today, 6) && (card.weekday === 6 || card.weekday === 0);
    case "pick_date":
      return !state.date || card.date === state.date;
    default:
      return true;
  }
}

function tagMatches(choice: string, values: string[]): boolean {
  if (!choice) return true;
  const [mode, id] = choice.split(":");
  if (mode === "only") return values.includes(id);
  if (mode === "hide") return !values.includes(id);
  return true;
}

/**
 * True when the card passes every filter that is on.
 * `today` is the local date in the city's time zone; `saved` is the set of
 * ids saved on this device.
 */
export function matches(card: CardFacts, state: FilterState, today: string, saved: ReadonlySet<string>): boolean {
  return (
    dayMatches(card, state, today) &&
    (!state.time || card.time === state.time) &&
    (!state.area || card.area === state.area) &&
    (!state.cause || card.cause === state.cause) &&
    (!state.type || card.type === state.type) &&
    (!state.join || card.join === state.join) &&
    tagMatches(state.host, card.host ? [card.host] : []) &&
    (!state.faith || card.faith === state.faith) &&
    tagMatches(state.activity, card.activities) &&
    (!state.no_training || card.training === "false") &&
    (!state.spanish || card.spanish === "true") &&
    (!state.saved || saved.has(card.id))
  );
}
