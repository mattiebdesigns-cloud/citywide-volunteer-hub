// Finds interface text that is missing from the translation files
// (PROJECT.md 5). The translation helper shows a missing key as the key
// itself, for example "listing.save", so this reads the built pages in
// dist/ and lists every key name that appears in them.
// Run after a build, from site/:  node scripts/check-strings.mjs
// Exit code 0 means none; 1 lists the missing keys for pv-languages.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");
const en = JSON.parse(readFileSync(join(root, "src/i18n/en.json"), "utf8"));
const spaces = Object.keys(en).join("|");
const pattern = new RegExp(`(?<![\\w./-])(?:${spaces})\\.[a-z_][a-z0-9_.-]*[a-z0-9_]`, "g");

function* files(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) yield* files(path);
    else if (/\.(html|txt)$/.test(name)) yield path;
  }
}

const found = new Map();
for (const path of files(dist)) {
  // Drop scripts and URLs, then look in text and attribute values.
  const text = readFileSync(path, "utf8").replace(/<script[\s\S]*?<\/script>/g, "").replace(/(href|src)="(?!mailto:)[^"]*"/g, "");
  for (const key of text.match(pattern) ?? []) {
    if (!found.has(key)) found.set(key, path.slice(dist.length + 1));
  }
}
if (found.size) {
  console.error(`Keys used by the pages but missing from the translation files (${found.size}):`);
  for (const [key, page] of [...found].sort()) console.error(`  ${key}   (first seen in ${page})`);
  process.exit(1);
}
console.log("Every key the pages use is in the translation files.");
