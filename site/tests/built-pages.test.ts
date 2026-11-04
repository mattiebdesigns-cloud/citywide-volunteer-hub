// Built pages: link-preview tags and robots.txt (decision 0014; decision 0009;
// PROJECT.md 8.1), and the card place line for screen readers (decision 0013).
// Run from site/: npm test. The build tests build the site into a temporary
// folder from the sample listings, moved into the future so they never expire.
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createI18n } from "../src/i18n/index.ts";
import { cityName, previewTags, robotsTxt, type MetaTag } from "../src/lib/og.ts";
import type { EventsFile, SiteSettings } from "../src/lib/types.ts";

const site = fileURLToPath(new URL("..", import.meta.url));
const settings: SiteSettings = JSON.parse(readFileSync(join(site, "settings.example.json"), "utf8"));
const sample: EventsFile = JSON.parse(readFileSync(join(site, "../docs/examples/events.sample.json"), "utf8"));
const languageFiles = Object.fromEntries(
  ["en", "es"].map((code) => [code, JSON.parse(readFileSync(join(site, `src/i18n/${code}.json`), "utf8"))]),
);
const i18n = createI18n(settings, languageFiles);
const URL_ = "https://volunteer.cedarwater.net";

const get = (tags: MetaTag[], key: string) => tags.filter((m) => m.key === key).map((m) => m.content);

// ---- Plain functions ----

test("{city} is the city's main area, not the region", () => {
  assert.equal(cityName(i18n.translator("en"), settings), "Philadelphia");
  assert.equal(cityName(i18n.translator("es"), settings), "Filadelfia");
});

test("tags with a site address: full addresses, picture in the page's language", () => {
  const tags = previewTags({
    lang: "es",
    languages: ["en", "es"],
    siteName: "Site",
    title: "Site",
    description: "D",
    imageAlt: "Alt",
    path: "/es/",
    siteUrl: URL_,
  });
  assert.deepEqual(get(tags, "og:url"), [`${URL_}/es/`]);
  assert.deepEqual(get(tags, "og:image"), [`${URL_}/og/es.png`]);
  assert.deepEqual(get(tags, "og:image:width"), ["1200"]);
  assert.deepEqual(get(tags, "og:image:height"), ["630"]);
  assert.deepEqual(get(tags, "og:image:alt"), ["Alt"]);
  assert.deepEqual(get(tags, "og:locale"), ["es_US"]);
  assert.deepEqual(get(tags, "og:locale:alternate"), ["en_US"]);
  assert.deepEqual(get(tags, "twitter:card"), ["summary_large_image"]);
  assert.ok(tags.every((m) => !m.content.includes("undefined")));
});

test("no site address: og:url and og:image are left out, the rest stays", () => {
  const tags = previewTags({
    lang: "en",
    languages: ["en", "es"],
    siteName: "Site",
    title: "T",
    description: "D",
    imageAlt: "Alt",
    path: "/en/",
    siteUrl: "",
  });
  const keys = tags.map((m) => m.key);
  for (const gone of ["og:url", "og:image", "og:image:width", "og:image:height", "og:image:alt"]) {
    assert.ok(!keys.includes(gone), gone);
  }
  for (const kept of ["og:type", "og:site_name", "og:title", "og:description", "og:locale", "twitter:card"]) {
    assert.ok(keys.includes(kept), kept);
  }
});

test("robots.txt: a test build lets in only Facebook's preview bot; production is unchanged", () => {
  assert.equal(robotsTxt(false), "User-agent: *\nAllow: /\n");
  const test = robotsTxt(true);
  assert.equal(test, "User-agent: facebookexternalhit\nAllow: /\n\nUser-agent: *\nDisallow: /\n");
  // Exactly one Allow, and it is in Facebook's group.
  assert.equal(test.match(/Allow: \//g)?.length, 1);
  assert.match(test, /User-agent: \*\nDisallow: \/\n$/);
});

// ---- Real builds ----

/** Moves a time 100 years ahead, so the build never drops the listing as past. */
const shift = (iso: string) => iso.replace(/^20(\d\d)/, (_, yy) => `21${yy}`);

/** The sample listings, moved 100 years ahead. */
function futureEvents(dir: string, edit?: (file: EventsFile) => void): string {
  const file = structuredClone(sample);
  edit?.(file);
  for (const e of file.events) {
    e.start = shift(e.start);
    if (e.end) e.end = shift(e.end);
  }
  const path = join(dir, "events.json");
  writeFileSync(path, JSON.stringify(file));
  return path;
}

function build(env: Record<string, string>, edit?: (file: EventsFile) => void): { out: string; read: (p: string) => string; done: () => void } {
  const dir = mkdtempSync(join(tmpdir(), "pv-preview-"));
  const out = join(dir, "dist");
  const clean = { ...process.env };
  delete clean.PV_SITE_URL;
  delete clean.PV_TEST_BUILD;
  execFileSync(join(site, "node_modules/.bin/astro"), ["build", "--outDir", out, "--silent"], {
    cwd: site,
    env: { ...clean, ASTRO_TELEMETRY_DISABLED: "1", PV_EVENTS: futureEvents(dir, edit), ...env },
    stdio: "pipe",
  });
  return { out, read: (p) => readFileSync(join(out, p), "utf8"), done: () => rmSync(dir, { recursive: true, force: true }) };
}

const decode = (s: string) =>
  s.replace(/&#39;|&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");

/** Preview tags in a built page, as [key, content] pairs. */
function tagsIn(html: string): [string, string][] {
  const head = html.slice(0, html.indexOf("</head>"));
  return [...head.matchAll(/<meta (?:property|name)="((?:og|twitter):[^"]+)" content="([^"]*)"/g)].map((m) => [m[1], decode(m[2])]);
}
const one = (tags: [string, string][], key: string) => {
  const found = tags.filter(([k]) => k === key).map(([, v]) => v);
  assert.equal(found.length, 1, `${key} once`);
  return found[0];
};

/** The page's visible text: the body, with scripts, styles and tags removed. */
function bodyText(html: string): string {
  const body = html.slice(html.indexOf("<body"));
  return decode(
    body
      .replace(/<script[\s\S]*?<\/script>/g, " ")
      .replace(/<style[\s\S]*?<\/style>/g, " ")
      .replace(/<[^>]+>/g, " "),
  ).replace(/\s+/g, " ");
}

const sensitive = sample.events.find((e) => e.sensitive === true || e.type === "protest_action");
const plain = sample.events.find((e) => e.sensitive !== true && e.type !== "protest_action");

test("test build with a site address: home, listing, sensitive listing, root, 404 and robots.txt", () => {
  const b = build({ PV_TEST_BUILD: "1", PV_SITE_URL: URL_ });
  try {
    // Home, in each language.
    for (const lang of ["en", "es"]) {
      const tr = i18n.translator(lang);
      const html = b.read(`${lang}/index.html`);
      const tags = tagsIn(html);
      assert.equal(one(tags, "og:title"), tr.setting(settings.site.name));
      assert.equal(one(tags, "og:description"), tr.t("og.description", { city: cityName(tr, settings) }));
      assert.equal(one(tags, "og:url"), `${URL_}/${lang}/`);
      assert.equal(one(tags, "og:image"), `${URL_}/og/${lang}.png`);
      assert.equal(one(tags, "og:image:alt"), tr.t("og.image_alt", { city: cityName(tr, settings) }));
      assert.equal(one(tags, "og:locale"), `${lang}_US`);
      assert.equal(one(tags, "twitter:card"), "summary_large_image");
      assert.match(html, /<meta name="robots" content="noindex, nofollow"/);
    }

    // Listing pages, plain and sensitive (decision 0014, owner Q38): the same
    // preview as the home page in that language, apart from og:url. No
    // title, date, organization or other listing detail in any meta tag.
    const en = i18n.translator("en");
    assert.ok(plain, "the sample has a plain listing");
    assert.ok(sensitive, "the sample has a sensitive listing");
    for (const listing of [plain, sensitive]) {
      for (const lang of ["en", "es"]) {
        const tr = i18n.translator(lang);
        const html = b.read(`${lang}/listing/${listing.id}/index.html`);
        const tags = tagsIn(html);
        const home = tagsIn(b.read(`${lang}/index.html`));
        const notUrl = (t: [string, string][]) => t.filter(([k]) => k !== "og:url");
        assert.deepEqual(notUrl(tags), notUrl(home), `${lang} ${listing.id}: same as home`);
        assert.equal(one(tags, "og:url"), `${URL_}/${lang}/listing/${listing.id}/`);
        // og:title is always there, so Facebook never falls back to <title>.
        assert.equal(one(tags, "og:title"), tr.setting(settings.site.name));
        assert.match(html, /<meta name="robots" content="noindex, nofollow"/);

        const details = [
          listing.title,
          listing.org_name,
          listing.start,
          shift(listing.start),
          tr.formatDate(shift(listing.start)),
          listing.address,
          listing.neighborhood_or_town,
          listing.signup_url,
        ].filter((d): d is string => typeof d === "string" && d.length > 0);
        const head = decode(html.slice(0, html.indexOf("</head>")));
        const metas = [...head.matchAll(/<meta [^>]*>/g)].map((m) => m[0]).filter((m) => !m.includes('property="og:url"'));
        for (const meta of metas) {
          for (const d of details) assert.ok(!meta.includes(d), `${lang} ${listing.id}: "${d}" is not in ${meta}`);
        }
      }
    }

    // Root language picker and 404: home-style, in English.
    for (const page of ["index.html", "404.html"]) {
      const tags = tagsIn(b.read(page));
      assert.equal(one(tags, "og:title"), en.setting(settings.site.name), page);
      assert.equal(one(tags, "og:description"), en.t("og.description", { city: "Philadelphia" }), page);
      assert.equal(one(tags, "og:locale"), "en_US", page);
      assert.equal(one(tags, "og:image"), `${URL_}/og/en.png`, page);
      assert.equal(one(tags, "og:url"), `${URL_}/`, page);
    }

    assert.equal(b.read("robots.txt"), robotsTxt(true));
  } finally {
    b.done();
  }
});

test("normal build with no site address: no og:url or og:image anywhere; robots.txt lets everyone in", () => {
  const b = build({});
  try {
    for (const page of ["index.html", "404.html", "en/index.html", "es/index.html", `en/listing/${plain!.id}/index.html`]) {
      const tags = tagsIn(b.read(page));
      const keys = tags.map(([k]) => k);
      assert.ok(keys.includes("og:title"), page);
      assert.ok(!keys.some((k) => k === "og:url" || k.startsWith("og:image")), page);
      assert.doesNotMatch(b.read(page), /noindex/, page);
    }
    assert.equal(b.read("robots.txt"), "User-agent: *\nAllow: /\n");
  } finally {
    b.done();
  }
});

test("card place line: screen readers hear the comma form; the dotted form is hidden from them", () => {
  const b = build({});
  try {
    const pair = sample.events.find((e) => e.section === "river-wards" && e.neighborhood_or_town === "Kensington");
    assert.ok(pair, "the sample has a River Wards, Kensington listing");
    for (const lang of ["en", "es"]) {
      const tr = i18n.translator(lang);
      const html = b.read(`${lang}/index.html`);
      const card = html.slice(html.indexOf(`/${lang}/listing/${pair.id}/`));
      const line = card.slice(0, card.indexOf("</p>", card.indexOf("Kensington")) + 4);
      const vars = { section: "River Wards", neighborhood: "Kensington" };
      const shown = tr.t("listing.place_pair", vars);
      const spoken = tr.t("listing.place_pair_spoken", vars);
      assert.equal(spoken, "River Wards, Kensington");
      assert.match(line, new RegExp(`<span aria-hidden="true"[^>]*>${shown}</span>`));
      assert.match(line, new RegExp(`<span class="sr-only"[^>]*>${spoken}</span>`));
    }
  } finally {
    b.done();
  }
});

test("cards show the hosting organization as it writes it, marked with the listing's language", () => {
  const LONG = "Schuylkill Center for Environmental Education";
  const longId = sample.events[0].id;
  const b = build({}, (file) => {
    file.events[0].org_name = LONG;
  });
  try {
    for (const lang of ["en", "es"]) {
      const tr = i18n.translator(lang);
      const html = b.read(`${lang}/index.html`);
      // Every card, sensitive ones too, has the line, right under the title.
      for (const e of sample.events) {
        const start = html.indexOf(`data-listing-id="${e.id}"`);
        assert.ok(start > 0, `${lang}: card ${e.id}`);
        const card = html.slice(start, html.indexOf("</article>", start));
        const org = e.id === longId ? LONG : e.org_name;
        const [before, after] = tr.t("listing.hosted_by").split("{org}");
        const line = card.match(/<p class="card__line card__host[^"]*"[^>]*>([\s\S]*?)<\/p>/);
        assert.ok(line, `${lang} ${e.id}: host line`);
        assert.equal(decode(line[1].replace(/<[^>]+>/g, "")).replace(/\s+/g, " ").trim(), `${before}${org}${after}`.trim());
        // The name carries the listing's own language, like the title.
        assert.match(line[1], new RegExp(`<span lang="${e.listing_language}"[^>]*>${org.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}</span>`));
        // Under the title and before the time and place lines.
        assert.ok(card.indexOf("card__title") < card.indexOf("card__host"));
        assert.ok(card.indexOf("card__host") < card.indexOf('name="clock"') || card.indexOf("card__host") < card.indexOf("<time"));
        // Not part of the link's name: the link holds the title only.
        const link = card.match(/<a class="card__link"[^>]*>([\s\S]*?)<\/a>/);
        assert.ok(link && !link[1].includes(org), `${lang} ${e.id}: link name is the title only`);
      }
    }
    // Long names wrap: the host line may break anywhere and is never clipped to one line.
    const css = readFileSync(new URL("../src/components/ui/ListingCard.astro", import.meta.url), "utf8");
    const rule = css.match(/\.card__host\s*\{([^}]*)\}/);
    assert.ok(rule, "card__host has a style rule");
    assert.match(rule[1], /overflow-wrap:\s*anywhere/);
    assert.doesNotMatch(rule[1], /nowrap|ellipsis|line-clamp/);
  } finally {
    b.done();
  }
});
