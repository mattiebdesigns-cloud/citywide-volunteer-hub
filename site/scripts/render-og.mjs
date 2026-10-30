// Draws the link-preview picture, one per language (decision 0014; PROJECT.md section 5).
//
//   node scripts/render-og.mjs          (run from site/)
//
// Reads the words from og.headline and og.tagline in src/i18n/<lang>.json, fills
// {city} with the area's name from the settings file (PV_SETTINGS, or
// settings.example.json), puts them into scripts/og/template.svg, and saves
// public/og/<lang>.png at 1200 x 630 using the Google Chrome already on this Mac.
// No packages, no outside fonts (system-ui only). Stops with an error if a word,
// the area or Chrome is missing, or if a picture comes out the wrong size.
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync, rmSync, statSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const site = resolve(fileURLToPath(new URL("..", import.meta.url)));
const CHROME = process.env.PV_CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const AREA_ID = "philadelphia";
const WIDTH = 1200, HEIGHT = 630, MAX_BYTES = 300 * 1024;

const fail = (msg) => { console.error(`render-og: ${msg}`); process.exit(1); };

const settingsPath = process.env.PV_SETTINGS
  ? resolve(process.cwd(), process.env.PV_SETTINGS)
  : join(site, "settings.example.json");
const settings = JSON.parse(readFileSync(settingsPath, "utf8"));
const area = (settings.areas || []).find((a) => a.id === AREA_ID);
if (!area) fail(`area "${AREA_ID}" not found in ${settingsPath}`);
const languages = settings.languages?.available || ["en", "es"];

const word = (dict, key, lang) => {
  const value = key.split(".").reduce((o, k) => (o == null ? undefined : o[k]), dict);
  if (typeof value !== "string" || !value.trim()) fail(`missing words: "${key}" in src/i18n/${lang}.json`);
  return value;
};
const escapeXml = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const template = readFileSync(join(site, "scripts/og/template.svg"), "utf8");

// The page Chrome photographs: the SVG, the text styles, and a few lines that
// shrink the headline until every word fits its box (Spanish runs longer).
const page = (lang, svg) => `<!doctype html>
<html lang="${lang}"><head><meta charset="utf-8">
<style>
  html, body { margin: 0; width: ${WIDTH}px; height: ${HEIGHT}px; overflow: hidden; background: #15294a; }
  svg { display: block; }
  .words { box-sizing: border-box; width: 540px; height: 490px; display: flex; flex-direction: column;
           justify-content: center; font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", "Helvetica Neue", Arial, sans-serif; }
  .bar { width: 88px; height: 10px; border-radius: 5px; background: #f08a6c; margin: 0 0 28px; }
  h1 { margin: 0; color: #ffffff; font-size: 80px; font-weight: 800; line-height: 1.04; letter-spacing: -0.015em;
       text-wrap: balance; overflow-wrap: normal; hyphens: none; }
  p { margin: 30px 0 0; color: #f08a6c; font-size: 42px; font-weight: 700; line-height: 1.15; text-wrap: balance; }
</style></head><body>
${svg}
<script>
  const box = document.querySelector(".words"), h = document.getElementById("headline"), t = document.getElementById("tagline");
  const tooBig = () => box.scrollHeight > box.clientHeight || h.scrollWidth > h.clientWidth || t.scrollWidth > t.clientWidth;
  let size = 80;
  while (tooBig() && size > 40) { size -= 2; h.style.fontSize = size + "px"; t.style.fontSize = Math.min(42, Math.round(size * 0.55)) + "px"; }
  if (tooBig()) { const ti = document.createElement("title"); ti.textContent = "OVERFLOW"; document.head.append(ti); }
</script>
</body></html>`;

const pngSize = (file) => {
  const b = readFileSync(file);
  if (b.toString("ascii", 1, 4) !== "PNG") fail(`${file} is not a PNG`);
  return [b.readUInt32BE(16), b.readUInt32BE(20)];
};

const outDir = join(site, "public/og");
mkdirSync(outDir, { recursive: true });
const work = mkdtempSync(join(tmpdir(), "pv-og-"));
try {
  for (const lang of languages) {
    const dict = JSON.parse(readFileSync(join(site, `src/i18n/${lang}.json`), "utf8"));
    const city = area.name?.[lang] || fail(`area "${AREA_ID}" has no ${lang} name`);
    const headline = word(dict, "og.headline", lang).replaceAll("{city}", city);
    const tagline = word(dict, "og.tagline", lang).replaceAll("{city}", city);
    const svg = template
      .replace(/<!--[\s\S]*?-->/g, "")
      .replaceAll("{{LANG}}", lang)
      .replaceAll("{{HEADLINE}}", escapeXml(headline))
      .replaceAll("{{TAGLINE}}", escapeXml(tagline));
    const htmlFile = join(work, `${lang}.html`);
    writeFileSync(htmlFile, page(lang, svg));
    const out = join(outDir, `${lang}.png`);
    try {
      execFileSync(CHROME, [
        "--headless", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
        "--force-device-scale-factor=1", `--user-data-dir=${join(work, "chrome")}`,
        `--window-size=${WIDTH},${HEIGHT}`, `--screenshot=${out}`, pathToFileURL(htmlFile).href,
      ], { stdio: "pipe" });
    } catch (e) {
      fail(`Chrome could not draw ${lang}.png (${e.message.split("\n")[0]}). Is Google Chrome installed?`);
    }
    // Second look, as text: did every word fit without shrinking past 40 px?
    const dom = execFileSync(CHROME, [
      "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
      `--user-data-dir=${join(work, "chrome")}`, `--window-size=${WIDTH},${HEIGHT}`,
      "--dump-dom", pathToFileURL(htmlFile).href,
    ], { stdio: ["ignore", "pipe", "pipe"] }).toString();
    if (dom.includes("<title>OVERFLOW</title>")) fail(`the ${lang} words do not fit the picture; shorten og.headline or og.tagline`);
    const [w, h] = pngSize(out);
    const bytes = statSync(out).size;
    if (w !== WIDTH || h !== HEIGHT) fail(`${out} is ${w} x ${h}, not ${WIDTH} x ${HEIGHT}`);
    if (bytes > MAX_BYTES) fail(`${out} is ${Math.round(bytes / 1024)} KB, over 300 KB`);
    console.log(`${lang}: public/og/${lang}.png  ${w} x ${h}  ${Math.round(bytes / 1024)} KB  "${headline}" / "${tagline}"`);
  }
} finally {
  rmSync(work, { recursive: true, force: true });
}
