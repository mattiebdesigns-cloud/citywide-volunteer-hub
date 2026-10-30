// Link previews (decision 0014) and robots.txt (decision 0009 as changed by 0014).
// Plain functions so tests can check them without a build.
import type { Translator } from "../i18n/index.ts";
import type { SiteSettings } from "./types.ts";

/** One <meta> tag. Open Graph tags use `property`, Twitter tags use `name`. */
export interface MetaTag {
  attr: "property" | "name";
  key: string;
  content: string;
}

export interface PreviewInput {
  /** The page's language. */
  lang: string;
  /** Every language the site offers. */
  languages: string[];
  siteName: string;
  /** Preview title. Home-style pages use the site name. */
  title: string;
  description: string;
  imageAlt: string;
  /** The page's own path, such as /en/ or /es/listing/abc/. */
  path: string;
  /** The site's public address with no trailing slash, or "" when not set. */
  siteUrl: string;
}

/** Facebook's locale codes: language plus country. The calendar is a US site. */
export function ogLocale(lang: string): string {
  return `${lang}_US`;
}

/**
 * The name `{city}` stands for in the og.* text: the area the city's sections
 * belong to ("Philadelphia"), not the region ("Greater Philadelphia").
 * Falls back to the first live area, then to the region.
 */
export function cityName(tr: Translator, settings: SiteSettings): string {
  const areaId = settings.sections?.[0]?.area ?? settings.areas.find((a) => a.live)?.id;
  return tr.areaName(areaId) || tr.setting(settings.site.region);
}

/**
 * Open Graph and Twitter tags for one page. Without a site address, og:url and
 * og:image are left out: Facebook needs full web addresses, and a relative one
 * would not work.
 */
export function previewTags(p: PreviewInput): MetaTag[] {
  const og = (key: string, content: string): MetaTag => ({ attr: "property", key, content });
  const tags: MetaTag[] = [
    og("og:type", "website"),
    og("og:site_name", p.siteName),
    og("og:title", p.title),
    og("og:description", p.description),
  ];
  if (p.siteUrl) tags.push(og("og:url", p.siteUrl + p.path));
  tags.push(og("og:locale", ogLocale(p.lang)));
  for (const other of p.languages) if (other !== p.lang) tags.push(og("og:locale:alternate", ogLocale(other)));
  if (p.siteUrl) {
    tags.push(
      og("og:image", `${p.siteUrl}/og/${p.lang}.png`),
      og("og:image:width", "1200"),
      og("og:image:height", "630"),
      og("og:image:alt", p.imageAlt),
    );
  }
  tags.push({ attr: "name", key: "twitter:card", content: "summary_large_image" });
  return tags;
}

/**
 * robots.txt. A test build lets in only Facebook's link-preview bot, so shared
 * links show a picture; every other crawler stays out (decision 0014). A
 * normal build lets everyone in.
 */
export function robotsTxt(testBuild: boolean): string {
  if (!testBuild) return "User-agent: *\nAllow: /\n";
  return "User-agent: facebookexternalhit\nAllow: /\n\nUser-agent: *\nDisallow: /\n";
}
