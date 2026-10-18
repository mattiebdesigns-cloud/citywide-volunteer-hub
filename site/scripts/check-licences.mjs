// Licence check for the site's npm packages (PROJECT.md section 3, rule 8).
//
// Reads package-lock.json and every installed package's package.json.
// Fails when a package's licence is not on the allowed list, or cannot be read.
// Standard library only. Run from site/:  node scripts/check-licences.mjs
import { readFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
// Allowed: MIT, Apache-2.0, BSD, ISC, PSF-2.0 (decision 0003), and
// Python-2.0, BlueOak-1.0.0 and CC0-1.0 (owner's answer to Q29, PROJECT.md v30
// sections 3 and 14). MPL, LGPL, GPL, AGPL and source-available stay blocked:
// they are simply not on this list.
const ALLOWED = new Set([
  "MIT", "MIT-0", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "0BSD", "ISC", "PSF-2.0",
  "Python-2.0", "BlueOak-1.0.0", "CC0-1.0",
]);

/**
 * True when an SPDX expression can be met using only allowed licences.
 * Brackets group; AND binds tighter than OR; AND needs every part, OR needs
 * one; "X WITH exception" is judged by X. Anything unreadable is not allowed.
 * Same rules as tests/guards/licence_check.py.
 */
function allowed(expression) {
  const tokens = expression.match(/\(|\)|[^\s()]+/g) ?? [];
  let i = 0;
  const peek = () => (tokens[i] ?? "").toUpperCase();
  const take = () => {
    if (i >= tokens.length) throw new Error("expression ends too early");
    return tokens[i++];
  };
  const orExpr = () => {
    let result = andExpr();
    while (peek() === "OR") { take(); result = andExpr() || result; }
    return result;
  };
  const andExpr = () => {
    let result = atom();
    while (peek() === "AND") { take(); result = atom() && result; }
    return result;
  };
  const atom = () => {
    const token = take();
    if (token === "(") {
      const result = orExpr();
      if (take() !== ")") throw new Error("missing )");
      return result;
    }
    if ([")", "AND", "OR", "WITH"].includes(token.toUpperCase())) throw new Error(`unexpected ${token}`);
    if (peek() === "WITH") { take(); take(); }
    return ALLOWED.has(token.replace(/\+$/, ""));
  };
  try {
    const result = orExpr();
    return i === tokens.length && result;
  } catch {
    return false;
  }
}

// Self-check, so a broken reader fails here rather than letting a package through.
for (const [expression, expected] of [
  ["MIT", true], ["MIT OR Apache-2.0", true], ["(MIT OR Apache-2.0) AND BSD-3-Clause", true],
  ["BlueOak-1.0.0", true], ["CC0-1.0", true], ["Python-2.0", true],
  ["MIT AND MPL-2.0", false], ["GPL-3.0-only AND (MIT OR Apache-2.0)", false],
  ["LGPL-3.0-only", false], ["AGPL-3.0-only", false], ["MPL-2.0", false], ["(MIT", false],
]) {
  if (allowed(expression) !== expected) {
    console.error(`check-licences.mjs is broken: "${expression}" should be ${expected ? "allowed" : "blocked"}`);
    process.exit(1);
  }
}

const lock = JSON.parse(readFileSync(join(root, "package-lock.json"), "utf8"));
const problems = [];
let count = 0;
for (const [path, entry] of Object.entries(lock.packages ?? {})) {
  if (!path) continue; // the site itself
  if (entry.link) continue;
  count += 1;
  let licence = entry.license;
  const manifest = join(root, path, "package.json");
  if (!licence && existsSync(manifest)) {
    const pkg = JSON.parse(readFileSync(manifest, "utf8"));
    licence = typeof pkg.license === "string" ? pkg.license : pkg.license?.type;
  }
  if (!licence) problems.push(`${path}: no licence found`);
  else if (!allowed(licence)) problems.push(`${path}: ${licence}`);
}
if (problems.length) {
  console.error(`Packages without an allowed licence (${problems.length}):`);
  for (const p of problems) console.error(`  ${p}`);
  process.exit(1);
}
console.log(`All ${count} packages have an allowed licence.`);
