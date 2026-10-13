#!/usr/bin/env node
// Key-parity check for the interface text (PROJECT.md section 5).
// No dependencies. Run: node site/src/i18n/check-keys.mjs
// Exits 1, with a plain list of problems, when any language file:
//   - is missing a key that en.json has, or has a key en.json does not have
//   - has an empty value or a value that is not text
//   - uses different {placeholders} from en.json for the same key
//   - lacks a plural form (keys ending .one, .other, ...) that it needs
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const dir = process.argv[2] ?? dirname(fileURLToPath(import.meta.url));
const REFERENCE = "en";
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

if (problems.length) {
  console.error(`Interface text check failed (${problems.length} problem${problems.length === 1 ? "" : "s"}):`);
  for (const p of problems) console.error(`  - ${p}`);
  process.exit(1);
}
console.log(`Interface text check passed: ${files.join(", ")} have matching keys.`);
