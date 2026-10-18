// Build-time inputs for every page: settings, listings, language helpers.
// Read once per build. Paths come from astro.config.mjs (PV_EVENTS, PV_SETTINGS).
import { readFileSync } from "node:fs";
import { createI18n, type I18n, type Translator } from "../i18n/index.ts";
import { catalogs } from "../i18n/locales.ts";
import { checkEventsFile, checkSettings, prepareListings } from "./prepare.ts";
import type { EventsFile, PreparedListing, SiteSettings } from "./types.ts";

export interface SiteData {
  settings: SiteSettings;
  i18n: I18n;
  listings: PreparedListing[];
  generatedAt: string;
  builtAt: Date;
  testBuild: boolean;
  /** The site's public address with no trailing slash, or "" when not set. */
  siteUrl: string;
}

let cached: SiteData | undefined;

function readJson<T>(path: string, what: string): T {
  let text: string;
  try {
    text = readFileSync(path, "utf8");
  } catch {
    throw new Error(`Cannot read the ${what} at ${path}`);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error(`The ${what} at ${path} is not valid JSON`);
  }
}

export function siteData(): SiteData {
  if (cached) return cached;
  const settingsPath = process.env.PV_SETTINGS_PATH;
  const eventsPath = process.env.PV_EVENTS_PATH;
  if (!settingsPath || !eventsPath) throw new Error("Build the site with astro.config.mjs (npm run build)");

  const settings = readJson<SiteSettings>(settingsPath, "settings file");
  checkSettings(settings, settingsPath);
  const file = readJson<EventsFile>(eventsPath, "events file");
  checkEventsFile(file, eventsPath);

  const builtAt = new Date();
  cached = {
    settings,
    i18n: createI18n(settings, catalogs),
    listings: prepareListings(file, settings, { now: builtAt }),
    generatedAt: file.generated_at,
    builtAt,
    testBuild: process.env.PV_TEST_BUILD === "1" || process.env.PV_TEST_BUILD === "true",
    siteUrl: (process.env.PV_SITE_URL ?? "").replace(/\/+$/, ""),
  };
  return cached;
}

/** Static paths for one page per language. */
export function languagePaths() {
  return siteData().i18n.languages.map((lang) => ({ params: { lang } }));
}

export function translator(lang: string): Translator {
  return siteData().i18n.translator(lang);
}

/** Page addresses. One place, so the language switch and links agree. */
export const paths = {
  home: (lang: string) => `/${lang}/`,
  listing: (lang: string, id: string) => `/${lang}/listing/${id}/`,
};
