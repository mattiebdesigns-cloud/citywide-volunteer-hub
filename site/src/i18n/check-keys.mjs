#!/usr/bin/env node
// Key-parity check for the interface text (PROJECT.md section 5).
// No dependencies. Run: node site/src/i18n/check-keys.mjs
// Optional settings check: pass a city's settings file as JSON, either
//   node site/src/i18n/check-keys.mjs --settings path/to/site.json
// or with the environment variable I18N_SETTINGS=path/to/site.json.
// Then every language in languages.available needs a file here, every cause id
// in causes, host_types, faith_traditions and activities needs a name in every
// language file (for example "causes.<id>"), and every area needs a name in
// every language.
// With no settings file (as in the public repo) that part is skipped.
// Exits 1, with a plain list of problems, when any language file:
//   - is missing a key that en.json has, or has a key en.json does not have
//   - has an empty value or a value that is not text
//   - uses different {placeholders} from en.json for the same key
//   - lacks a plural form (keys ending .one, .other, ...) that it needs
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const at = args.indexOf("--settings");
// Skip the settings check only when no settings option is given at all. A
// `--settings` with no value, or an I18N_SETTINGS that is set but empty,
// usually means a CI variable is missing, so it fails instead of passing quietly.
const settingsGiven = at >= 0 || "I18N_SETTINGS" in process.env;
const settingsPath = at >= 0 ? args[at + 1] : process.env.I18N_SETTINGS;
if (settingsGiven && (!settingsPath || !settingsPath.trim() || settingsPath.startsWith("--"))) {
  console.error(
    at >= 0
      ? "--settings needs a path to the settings file (JSON). It was given with no value."
      : "I18N_SETTINGS is set but empty. Give it a path to the settings file (JSON), or unset it to skip the settings check.",
  );
  process.exit(1);
}
const positional = args.filter((_, n) => at < 0 || (n !== at && n !== at + 1));
const dir = positional[0] ?? dirname(fileURLToPath(import.meta.url));
const REFERENCE = "en";
const NAMED_LISTS = [
  ["causes", "cause"],
  ["host_types", "host type"],
  ["faith_traditions", "faith tradition"],
  ["activities", "activity"],
];
const PLURALS = new Set(["zero", "one", "two", "few", "many", "other"]);
const problems = [];

function flatten(obj, prefix, file) {
  const out = {};
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") {
      if (value.trim() === "") problems.push(`${file}: "${path}" is empty`);
      out[path] = value;
    } else if (value && typeof value === "object" && !Array.isArray(value)) {
      Object.assign(out, flatten(value, path, file));
    } else {
      problems.push(`${file}: "${path}" must be text or a group of keys`);
    }
  }
  return out;
}

const placeholders = (text) => [...text.matchAll(/\{([a-z_]+)\}/g)].map((m) => m[1]).sort().join(",");

// Plural groups (results.count.one, results.count.other) are compared as a
// group: a group is any set of keys that are all plural forms and include
// "other". Each language needs "other", plus every form English has that the
// language also uses. Missing rarer forms fall back to "other" at run time.
function split(flat) {
  const groups = {};
  for (const [key, value] of Object.entries(flat)) {
    const dot = key.lastIndexOf(".");
    if (dot > 0) (groups[key.slice(0, dot)] ??= {})[key.slice(dot + 1)] = value;
  }
  const plural = {};
  for (const [group, forms] of Object.entries(groups)) {
    const names = Object.keys(forms);
    if ("other" in forms && names.every((n) => PLURALS.has(n))) plural[group] = forms;
  }
  const plain = {};
  for (const [key, value] of Object.entries(flat)) {
    if (!(key.slice(0, key.lastIndexOf(".")) in plural)) plain[key] = value;
  }
  return { plain, plural };
}

const files = readdirSync(dir).filter((f) => f.endsWith(".json")).sort();
const load = (f) => {
  try {
    return flatten(JSON.parse(readFileSync(join(dir, f), "utf8")), "", f);
  } catch (err) {
    problems.push(`${f}: not valid JSON (${err.message})`);
    return {};
  }
};

if (!files.includes(`${REFERENCE}.json`)) {
  console.error(`No ${REFERENCE}.json in ${dir}`);
  process.exit(1);
}
const ref = split(load(`${REFERENCE}.json`));

for (const file of files.filter((f) => f !== `${REFERENCE}.json`)) {
  const lang = file.replace(/\.json$/, "");
  const cur = split(load(file));
  for (const key of Object.keys(ref.plain)) {
    if (!(key in cur.plain)) problems.push(`${file}: missing "${key}"`);
    else if (placeholders(ref.plain[key]) !== placeholders(cur.plain[key]))
      problems.push(`${file}: "${key}" uses {${placeholders(cur.plain[key])}}, en.json uses {${placeholders(ref.plain[key])}}`);
  }
  for (const key of Object.keys(cur.plain))
    if (!(key in ref.plain)) problems.push(`${file}: "${key}" is not in en.json (remove it or add it there)`);

  let needed;
  try {
    needed = new Intl.PluralRules(lang).resolvedOptions().pluralCategories;
  } catch {
    needed = ["other"];
  }
  for (const key of Object.keys(ref.plural)) {
    const forms = cur.plural[key];
    if (!forms) {
      problems.push(`${file}: missing plural group "${key}"`);
      continue;
    }
    for (const form of Object.keys(ref.plural[key]).filter((f) => f === "other" || needed.includes(f)))
      if (!(form in forms)) problems.push(`${file}: "${key}.${form}" is needed for this language`);
    const want = placeholders(ref.plural[key].other ?? "");
    for (const [form, text] of Object.entries(forms))
      if (placeholders(text) !== want) problems.push(`${file}: "${key}.${form}" uses {${placeholders(text)}}, en.json uses {${want}}`);
  }
  for (const key of Object.keys(cur.plural))
    if (!(key in ref.plural)) problems.push(`${file}: plural group "${key}" is not in en.json`);
}

if (settingsPath) checkSettings(settingsPath);
else console.log("No settings file given: skipping the cause and area name check.");

function checkSettings(path) {
  const where = `settings (${path})`;
  if (!path.endsWith(".json")) {
    problems.push(`${where}: give the settings as JSON (convert site.yml first)`);
    return;
  }
  let settings;
  try {
    settings = JSON.parse(readFileSync(path, "utf8"));
  } catch (err) {
    problems.push(`${where}: cannot read it (${err.message})`);
    return;
  }
  const available = settings?.languages?.available ?? [];
  const texts = {};
  for (const lang of available) {
    if (!files.includes(`${lang}.json`)) problems.push(`${where}: languages.available lists "${lang}" but there is no ${lang}.json`);
    else texts[lang] = load(`${lang}.json`);
  }
  // Each settings list whose ids get their names from the language files.
  for (const [list, what] of NAMED_LISTS)
    for (const id of settings?.[list] ?? [])
      for (const [lang, flat] of Object.entries(texts))
        if (!flat[`${list}.${id}`]) problems.push(`${lang}.json: no name for ${what} "${id}" (add "${list}.${id}")`);
  for (const area of settings?.areas ?? []) {
    const name = area?.name;
    if (typeof name === "string" && name.trim()) continue;
    if (!name || typeof name !== "object") {
      problems.push(`${where}: area "${area?.id}" has no name`);
      continue;
    }
    for (const lang of available)
      if (typeof name[lang] !== "string" || !name[lang].trim())
        problems.push(`${where}: area "${area?.id}" has no ${lang} name`);
  }
}

if (problems.length) {
  console.error(`Interface text check failed (${problems.length} problem${problems.length === 1 ? "" : "s"}):`);
  for (const p of problems) console.error(`  - ${p}`);
  process.exit(1);
}
console.log(`Interface text check passed: ${files.join(", ")} have matching keys.`);
