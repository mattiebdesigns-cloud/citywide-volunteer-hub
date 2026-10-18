// Interface text for the calendar site (PROJECT.md section 5).
//
// No dependencies. Works at build time (Astro pages) and in the browser.
// Adding a language: add `<code>.json` next to this file and add the code to
// `languages.available` in the city's settings file. Nothing here changes.

/** One language file: nested objects whose leaves are strings. */
export type Messages = { [key: string]: string | Messages };

/**
 * A settings value that may differ by language. Either one string for every
 * language, or a map such as `{ en: "Greater Philadelphia", es: "..." }`.
 */
export type LocalizedText = string | { [lang: string]: string };

/** The parts of the city's settings file that this helper reads. */
export interface I18nSettings {
  site: {
    name: LocalizedText;
    region: LocalizedText;
    /** IANA time zone, e.g. "America/New_York". Needed to show dates and times. */
    timezone?: string;
    [key: string]: unknown;
  };
  /** Areas for the area filter. `id` matches `area` in each listing. */
  areas?: Array<{ id: string; name: LocalizedText; live?: boolean }>;
  /** Cause ids. `id` matches `cause` in each listing; names live in `causes.<id>` in the language files. */
  causes?: string[];
  /** Who runs a shift (`host_type`). Names live in `host_types.<id>`. */
  host_types?: string[];
  /** Only for faith-based hosts (`faith_tradition`). Names live in `faith_traditions.<id>`. */
  faith_traditions?: string[];
  /** What the work is like (`activity`, any number). Names live in `activities.<id>`. */
  activities?: string[];
  languages: {
    default: string;
    available: string[];
    /** `<code>_reviewed_by_fluent_speaker: true` removes the "beta" label. */
    [key: string]: unknown;
  };
}

/** Settings lists whose names come from the language files, keyed by id. */
export type NamedList = "causes" | "host_types" | "faith_traditions" | "activities";

export type Vars = Record<string, string | number>;

/** Browser storage key for the visitor's language choice. */
export const STORAGE_KEY = "cvh.language";

/** Turns `{ a: { b: "x" } }` into `{ "a.b": "x" }`. */
export function flatten(messages: Messages, prefix = ""): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(messages)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") out[path] = value;
    else Object.assign(out, flatten(value, path));
  }
  return out;
}

/** Replaces `{name}` with `vars.name`. Unknown placeholders stay visible. */
export function fill(text: string, vars: Vars = {}): string {
  return text.replace(/\{([a-z_]+)\}/g, (whole, name: string) =>
    name in vars ? String(vars[name]) : whole,
  );
}

/** Picks a settings value for one language, falling back to the default language. */
export function localize(value: LocalizedText, lang: string, fallback: string): string {
  if (typeof value === "string") return value;
  return value[lang] ?? value[fallback] ?? Object.values(value)[0] ?? "";
}

/**
 * Picks the first candidate that the site offers. Candidates are tried in
 * order, for example: the stored choice, then the browser's languages.
 * "es-MX" matches "es". Returns the default when nothing matches.
 */
export function pickLanguage(
  candidates: ReadonlyArray<string | null | undefined>,
  available: readonly string[],
  fallback: string,
): string {
  for (const candidate of candidates) {
    if (!candidate) continue;
    const code = candidate.toLowerCase().split(/[-_]/)[0];
    if (available.includes(code)) return code;
  }
  return fallback;
}

/** Reads the visitor's saved choice. Returns null if storage is blocked. */
export function readStoredLanguage(): string | null {
  try {
    return globalThis.localStorage?.getItem(STORAGE_KEY) ?? null;
  } catch {
    return null;
  }
}

/** Saves the visitor's choice in their own browser only. Never sent anywhere. */
export function storeLanguage(lang: string): void {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, lang);
  } catch {
    // Private browsing or storage turned off: the toggle still works for this page.
  }
}

export interface Translator {
  lang: string;
  /** True when this language still shows the "beta" label. */
  isBeta: boolean;
  /** Text for a key. Falls back to the default language, then to the key itself. */
  t(key: string, vars?: Vars): string;
  /** Text for a count, using the language's plural rules (`key.one`, `key.other`, ...). */
  plural(key: string, count: number, vars?: Vars): string;
  /** A settings value (such as the region) in this language. */
  setting(value: LocalizedText): string;
  /** An area's name in this language, from the settings file. Empty for null or an unknown id, so the page can skip it. */
  areaName(id: string | null | undefined): string;
  /** A cause's name in this language, from `causes.<id>` in the language files. Empty for null or an unknown id, so the page can skip it. */
  causeName(id: string | null | undefined): string;
  /** A name from one of the settings lists named in the language files. Empty for null or an unknown id. */
  listName(list: NamedList, id: string | null | undefined): string;
  /** A date with the month written out, so it cannot be misread. */
  formatDate(date: Date | string): string;
  /** The day of the week only, such as Monday or lunes. */
  formatWeekday(date: Date | string): string;
  /** A clock time, such as 6:30 PM or 6:30 p. m. */
  formatTime(date: Date | string): string;
  /** A number written the way this language writes it. */
  formatNumber(n: number): string;
}

export interface I18n {
  languages: string[];
  defaultLanguage: string;
  /** Each language's name in that language, for the toggle. */
  languageName(lang: string): string;
  isBeta(lang: string): boolean;
  translator(lang: string): Translator;
}

/**
 * Builds the helper from the settings file and the language files.
 * Throws at build time if the settings list a language that has no file,
 * so a broken setup never reaches visitors.
 */
export function createI18n(settings: I18nSettings, catalogs: Record<string, Messages>): I18n {
  const { default: defaultLanguage, available } = settings.languages;
  if (!available.includes(defaultLanguage)) {
    throw new Error(`languages.default "${defaultLanguage}" is not in languages.available`);
  }
  const flat: Record<string, Record<string, string>> = {};
  for (const lang of available) {
    const catalog = catalogs[lang];
    if (!catalog) {
      throw new Error(`languages.available lists "${lang}" but there is no ${lang}.json in site/src/i18n/`);
    }
    flat[lang] = flatten(catalog);
  }

  const isBeta = (lang: string): boolean =>
    lang !== defaultLanguage && settings.languages[`${lang}_reviewed_by_fluent_speaker`] !== true;

  const languageName = (lang: string): string => flat[lang]?.["language.name"] ?? lang;

  function translator(requested: string): Translator {
    const lang = available.includes(requested) ? requested : defaultLanguage;
    const own = flat[lang];
    const base = flat[defaultLanguage];
    const builtIn: Vars = {
      site_name: localize(settings.site.name, lang, defaultLanguage),
      region: localize(settings.site.region, lang, defaultLanguage),
    };
    const lookup = (key: string): string | undefined => own[key] ?? base[key];
    const t = (key: string, vars: Vars = {}): string => {
      const text = lookup(key);
      return text === undefined ? key : fill(text, { ...builtIn, ...vars });
    };

    function listName(list: NamedList, id: string | null | undefined): string {
      return id && lookup(`${list}.${id}`) !== undefined ? t(`${list}.${id}`) : "";
    }

    const pluralRules = new Intl.PluralRules(lang);
    const numbers = new Intl.NumberFormat(lang);
    const zone = (): string => {
      const tz = settings.site.timezone;
      if (!tz) throw new Error("site.timezone is missing from the settings file; dates cannot be shown");
      return tz;
    };
    // Clock style (6:30 PM or 18:30) follows the city's default language, so
    // every language on one site shows times the way local signs and flyers do.
    const hourCycle = new Intl.DateTimeFormat(defaultLanguage, { hour: "numeric" }).resolvedOptions().hourCycle;
    const asDate = (d: Date | string): Date => (typeof d === "string" ? new Date(d) : d);

    return {
      lang,
      isBeta: isBeta(lang),
      t,
      plural(key, count, vars = {}) {
        const category = pluralRules.select(count);
        const full = { count: numbers.format(count), ...vars };
        if (lookup(`${key}.${category}`) !== undefined) return t(`${key}.${category}`, full);
        return t(`${key}.other`, full);
      },
      setting: (value) => localize(value, lang, defaultLanguage),
      areaName: (id) => {
        const area = id ? settings.areas?.find((a) => a.id === id) : undefined;
        return area ? localize(area.name, lang, defaultLanguage) : "";
      },
      causeName: (id) => listName("causes", id),
      listName,
      formatDate: (d) =>
        new Intl.DateTimeFormat(lang, {
          weekday: "long",
          month: "long",
          day: "numeric",
          year: "numeric",
          timeZone: zone(),
        }).format(asDate(d)),
      formatWeekday: (d) =>
        new Intl.DateTimeFormat(lang, { weekday: "long", timeZone: zone() }).format(asDate(d)),
      formatTime: (d) =>
        new Intl.DateTimeFormat(lang, { hour: "numeric", minute: "2-digit", hourCycle, timeZone: zone() }).format(asDate(d)),
      formatNumber: (n) => numbers.format(n),
    };
  }

  return { languages: [...available], defaultLanguage, languageName, isBeta, translator };
}
