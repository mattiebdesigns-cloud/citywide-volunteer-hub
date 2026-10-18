# Interface text

Every word a visitor reads on the calendar site comes from the files in this folder: `en.json` for English, `es.json` for Spanish. Pages never contain typed-in text.

## Files

| File | What it does |
|---|---|
| `en.json`, `es.json` | The text, one file per language. English is the reference. |
| `index.ts` | Picks a language, fills `{placeholders}`, falls back to English for a missing key, formats dates and times, and says whether a language still shows "beta". No dependencies. |
| `locales.ts` | Loads every `<code>.json` here at build time (Astro). |
| `check-keys.mjs` | The build check. Fails when a key is missing or extra, when a value is empty, or when `{placeholders}` differ between languages. Run `node site/src/i18n/check-keys.mjs`. Add `--settings site.json` (or set `I18N_SETTINGS`) to also check that every cause, host type, faith tradition, activity and area in a city's settings file has a name in every language; the settings must be JSON. |

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
- Area names come from `areas[].name` in the settings file (`tr.areaName(id)`). Cause, host type, faith tradition and activity names come from `causes.<id>`, `host_types.<id>`, `faith_traditions.<id>` and `activities.<id>` in these files (`tr.causeName(id)`, or `tr.listName("activities", id)`). A city with different lists adds one key per id to every language file. Both return empty text for a missing or unknown id, so the page can leave it out.
- Dates and times need `site.timezone` in the settings file (for example `America/New_York`). Times use the clock style of the city's default language in every language, so they match local signs.
- The toggle shows each language in its own name (`language.name`). The visitor's choice is kept in their own browser (`storeLanguage`). It is never sent to us.
- A language other than the default shows "beta" until the settings file says `languages.<code>_reviewed_by_fluent_speaker: true`.
- Set `<html lang>` to the current language (`tr.lang`), so screen readers use the right voice.
- In the language picker, mark each option with its own language, for example `<a lang="es">Español</a>`.
- Listing text shown untranslated (titles, organization text) keeps the organization's language: wrap it in an element with `lang` set to the listing's `listing_language`.
- Put text on the page as plain text. Do not pass it through `set:html`.
- `filters.type.campaign` and `about.campaigns` exist in every build. Use them only when `features.campaigns` is on.

## Adding a language

1. Copy `en.json` to `<code>.json` (for example `fr.json`) and translate every value. Keep every `{placeholder}` as it is.
2. Add the code to `languages.available` in the settings file.

That is all. The check tells you about any key you missed. Until a fluent speaker reviews the file, the language shows "beta".

## Spanish review (required before launch)

**A fluent Spanish speaker has not yet reviewed `es.json`.** Until the settings file says `languages.es_reviewed_by_fluent_speaker: true`, the Spanish toggle stays marked "beta". The owner sets that value after the review.

The aim is plain, neutral Spanish for Latin American readers in the region, with no regional slang. Choices the reviewer should confirm:

- **Usted or tú.** Sentences use the formal *usted* (*Consulte*, *Reciba*). Buttons and filter options use infinitives (*Traducir*, *Inscribirse antes*).
- **Time of day.** *Por la mañana / Por la tarde / Por la noche / Toda la noche*. "Overnight" (*Toda la noche*) needs to read clearly as a shift that runs through the night, different from "evening".
- **How to join.** *Llegar sin inscribirse*, *Inscribirse antes*, *Solicitar antes*, *Consultar con el organizador*. Is *Solicitar antes* clear for "apply and wait for an answer"?
- **Words for the same thing everywhere.** listing = *anuncio*, shift = *turno*, sign up = *inscribirse*, report = *reportar / reporte* (common in the US and Latin America; Spain uses *informar*), training = *capacitación*, add = *agregar*.
- **Background checks.** *Requiere verificación de antecedentes* for "clearances" (a Pennsylvania term).
- **Cause names.** *Alimentos* (food), *Parques y árboles*, *Animales*, *Jóvenes* (youth), *Vivienda* (housing), *Personas mayores* (older adults), *Acción cívica*, *Educación*, *Salud*, *Ropa* (clothing), *Reparación* (repair, as in fixing items; would *Reparaciones* read more naturally?).
- **Region and area names** are in the city's settings file, not here. The Spanish reviewer checks them there.
- **Recurring events.** *Se repite con regularidad* for "Repeats on a schedule".
- **Who runs it.** *Organización sin fines de lucro*, *Agencia de gobierno*, *Comunidad de fe*, *Escuela o universidad*, *Ayuda mutua o grupo comunitario*, *Organizado por una empresa*. And `listing.business_led_note`: *Una empresa organizó esta jornada. La empresa puede presentar el trabajo que usted haga, y sus resultados, como logros propios.*
- **Faith traditions.** Feminine forms, to agree with *tradición*: *Cristiana*, *Musulmana*, *Judía*, *Budista*, *Hindú*, *Sij*, *Interreligiosa*, *Espiritual*, *Otra tradición*. Is *Sij* (the dictionary spelling) familiar enough, or is *Sikh* better?
- **What the work is like.** *Al aire libre*, *Bajo techo* (or *En interiores*?), *Trabajo físico (cargar cosas, estar de pie por horas)*, *Trabajo sentado*, *Con animales*, *Con niños*, *Trabajo en cocina*, *Desde casa o en línea*.
- **Filter words.** *Quién lo organiza*, *Tradición religiosa*, *Cómo es el trabajo*, *Mostrar solo*, *Ocultar*.
- **Rewards notice** (`site.rewards_coming`). *Las recompensas por hacer voluntariado llegan pronto. Por ahora, busque un turno en el que pueda participar.* Is *recompensas* the right word for the rewards?
- **Weekly email name.** *Esta semana en el voluntariado*.
- **`filters.join.unknown`.** *Consultar con el organizador* uses the masculine form for a generic organizer.
