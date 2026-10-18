// Shapes of the two build inputs (PROJECT.md sections 1, 3 and 4).
// The listing format is docs/EVENT-FORMAT.md; the settings are the city's
// settings file (config/site.yml in the private repo, converted to JSON).
import type { I18nSettings, LocalizedText } from "../i18n/index.ts";

export type JoinMethod = "drop_in" | "signup" | "application" | "unknown";
export type ListingType = "service" | "training" | "campaign" | "protest_action";
export type TimeOfDay = "morning" | "afternoon" | "evening" | "overnight";

export interface Listing {
  id: string;
  org_name: string;
  title: string;
  start: string;
  end: string | null;
  address: string | null;
  area: string;
  neighborhood_or_town: string | null;
  cause: string | null;
  type: ListingType;
  sensitive: boolean;
  photos_allowed: boolean;
  signup_url: string;
  join_method: JoinMethod;
  min_age: number | null;
  listing_language: string;
  spanish_spoken: boolean | "unknown";
  training_required: boolean | null;
  clearances_required: boolean | null;
  group_friendly: boolean | null;
  recurring: boolean;
  recurrence_rule: string | null;
  source_url: string;
  source_id: string;
  last_seen_at: string;
  host_type?: string | null;
  faith_tradition?: string | null;
  activity?: string[] | null;
  spots_left?: number | null;
  spots_total?: number | null;
  full?: boolean;
}

export interface EventsFile {
  generated_at: string;
  events: Listing[];
}

export interface SiteSettings extends I18nSettings {
  site: {
    name: LocalizedText;
    region: LocalizedText;
    timezone: string;
    contact_email: string;
    [key: string]: unknown;
  };
  areas: Array<{ id: string; name: LocalizedText; live?: boolean }>;
  time_of_day: Record<TimeOfDay, string>;
  causes: string[];
  host_types?: string[];
  faith_traditions?: string[];
  activities?: string[];
  features: { campaigns: boolean; [key: string]: unknown };
}

/** A listing plus facts worked out once at build time, in the city's time zone. */
export interface PreparedListing extends Listing {
  /** Local date of the start, YYYY-MM-DD. */
  localDate: string;
  /** Local weekday of the start, 0 = Sunday. */
  weekday: number;
  timeOfDay: TimeOfDay;
  /** True when the end falls on a later local date than the start. */
  endsNextDay: boolean;
  /** When the listing is over: end, or start when there is no end (milliseconds). */
  overAt: number;
}
