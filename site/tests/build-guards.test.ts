// Guards for packages replaced by empty stand-ins (PROJECT.md section 3:
// permissive licences only). Run from site/: npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";

const require = createRequire(import.meta.url);
const config = readFileSync(new URL("../astro.config.mjs", import.meta.url), "utf8");

test("the lightningcss stand-in is installed, never the real package (MPL-2.0)", () => {
  const pkg = JSON.parse(readFileSync(new URL("../node_modules/lightningcss/package.json", import.meta.url), "utf8"));
  assert.equal(pkg.version, "0.0.0-not-installed");
});

test("calling the lightningcss stand-in stops with a plain error", () => {
  const lightningcss = require("lightningcss");
  assert.throws(() => lightningcss.transform({}), /lightningcss is not installed/);
  assert.throws(() => lightningcss.bundle({}), /lightningcss is not installed/);
});

test("Vite is told never to call lightningcss", () => {
  assert.match(config, /transformer:\s*"postcss"/);
  assert.match(config, /cssMinify:\s*false/);
});

test("the sharp stand-in is installed and images are never processed (LGPL)", () => {
  const pkg = JSON.parse(readFileSync(new URL("../node_modules/sharp/package.json", import.meta.url), "utf8"));
  assert.equal(pkg.version, "0.0.0-not-installed");
  assert.match(config, /passthroughImageService\(\)/);
});
