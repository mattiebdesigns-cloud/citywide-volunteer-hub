// Dates and times in the city's own time zone (settings: site.timezone,
// time_of_day). Used at build time and in the browser. No dependencies.
import type { TimeOfDay } from "./types.ts";

export interface LocalParts {
  /** YYYY-MM-DD */
  date: string;
  /** 0 = Sunday */
  weekday: number;
  /** Minutes after local midnight. */
  minutes: number;
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const formatters = new Map<string, Intl.DateTimeFormat>();

function formatter(timeZone: string): Intl.DateTimeFormat {
  let f = formatters.get(timeZone);
  if (!f) {
    f = new Intl.DateTimeFormat("en-US", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      weekday: "short",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    });
    formatters.set(timeZone, f);
  }
  return f;
}

/** The local date, weekday and time of an instant in the given time zone. */
export function localParts(instant: Date | string | number, timeZone: string): LocalParts {
  const parts: Record<string, string> = {};
  for (const p of formatter(timeZone).formatToParts(new Date(instant))) parts[p.type] = p.value;
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    weekday: WEEKDAYS.indexOf(parts.weekday ?? ""),
    minutes: (Number(parts.hour) % 24) * 60 + Number(parts.minute),
  };
}

/** Adds whole days to a YYYY-MM-DD date. */
export function addDays(date: string, days: number): string {
  const [y, m, d] = date.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

/** "17:30" to minutes after midnight. */
export function clockToMinutes(clock: string): number {
  const match = /^(\d{1,2}):(\d{2})$/.exec(clock.trim());
  if (!match) throw new Error(`time_of_day: "${clock}" is not a time like 17:00`);
  return Number(match[1]) * 60 + Number(match[2]);
}

const ORDER: TimeOfDay[] = ["morning", "afternoon", "evening", "overnight"];

/**
 * Which time-of-day bucket a start time falls in. Each bucket runs from its
 * own start to the next one's; overnight runs until the next morning.
 */
export function timeOfDay(minutes: number, starts: Record<TimeOfDay, string>): TimeOfDay {
  const bounds = ORDER.map((name) => ({ name, at: clockToMinutes(starts[name]) }));
  for (let i = 1; i < bounds.length; i++) {
    if (bounds[i].at <= bounds[i - 1].at) {
      throw new Error("time_of_day: morning, afternoon, evening and overnight must start in that order");
    }
  }
  let found: TimeOfDay = "overnight"; // before morning starts
  for (const b of bounds) if (minutes >= b.at) found = b.name;
  return found;
}
