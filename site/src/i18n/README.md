# Interface text

Every word a visitor reads on the calendar site comes from the files in this folder: `en.json` for English, `es.json` for Spanish. Pages never contain typed-in text.

## Files

| File | What it does |
|---|---|
| `en.json`, `es.json` | The text, one file per language. English is the reference. |
| `index.ts` | Picks a language, fills `{placeholders}`, falls back to English for a missing key, formats dates and times, and says whether a language still shows "beta". No dependencies. |
| `locales.ts` | Loads every `<code>.json` here at build time (Astro). |
| `check-keys.mjs` | The build check. Fails when a key is missing or extra, when a value is empty, or when `{placeholders}` differ between languages. Run `node site/src/i18n/check-keys.mjs`. |

## Using it in a page

```ts
import { createI18n } from "../i18n";
import { catalogs } from "../i18n/locales";
const i18n = createI18n(settings, catalogs);   // settings = the city's settings file
const tr = i18n.translator("es");
tr.t("listing.last_checked", { date: tr.formatDate(event.last_seen_at) });
tr.plural("results.count", events.length);
tr.isBeta;                                     // show t("language.beta") next to the toggle
```

- The city name and region are never written into the text. `{site_name}` and `{region}` are filled from `site.name` and `site.region` in the settings file. Either value can be one string or a map by language, such as `region: {en: "...", es: "..."}`.
- Organization names, event titles and descriptions are never put through these files and never translated by the site. They go in as placeholders, such as `{org}`, exactly as the organization wrote them.
- Dates and times need `site.time_zone` in the settings file (for example `America/New_York`). Times use the clock style of the city's default language in every language, so they match local signs.
- The toggle shows each language in its own name (`language.name`). The visitor's choice is kept in their own browser (`storeLanguage`). It is never sent to us.
- A language other than the default shows "beta" until the settings file says `languages.<code>_reviewed_by_fluent_speaker: true`.
- Put text on the page as plain text. Do not pass it through `set:html`.
- `filters.type.campaign` and `about.campaigns` exist in every build. Use them only when `features.campaigns` is on.

## Adding a language

1. Copy `en.json` to `<code>.json` (for example `fr.json`) and translate every value. Keep every `{placeholder}` as it is.
2. Add the code to `languages.available` in the settings file.

That is all. The check tells you about any key you missed. Until a fluent speaker reviews the file, the language shows "beta".

## Spanish review (required before launch)

**A fluent Spanish speaker has not yet reviewed `es.json`.** Until the owner records that review in STATUS.md, the Spanish toggle stays marked "beta".

The aim is plain, neutral Spanish for Latin American readers in the region, with no regional slang. Choices the reviewer should confirm:

- **Usted or tú.** Sentences use the formal *usted* (*Consulte*, *Reciba*). Buttons and filter options use infinitives (*Traducir*, *Inscribirse antes*).
- **Time of day.** *Por la mañana / Por la tarde / Por la noche / Toda la noche*. "Overnight" (*Toda la noche*) needs to read clearly as a shift that runs through the night, different from "evening".
- **How to join.** *Llegar sin inscribirse*, *Inscribirse antes*, *Solicitar antes*, *Consultar con el organizador*. Is *Solicitar antes* clear for "apply and wait for an answer"?
- **Words for the same thing everywhere.** listing = *anuncio*, shift = *turno*, sign up = *inscribirse*, report = *reportar / reporte* (common in the US and Latin America; Spain uses *informar*), training = *capacitación*, add = *agregar*.
- **Background checks.** *Requiere verificación de antecedentes* for "clearances" (a Pennsylvania term).
- **Weekly email name.** *Esta semana en el voluntariado*.
- **`filters.join.unknown`.** *Consultar con el organizador* uses the masculine form for a generic organizer.
