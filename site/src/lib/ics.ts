// "Add to my calendar" file for one listing (PROJECT.md 2). RFC 5545.
//
// The file is made at build time and handed to the browser inside the page.
// The browser saves it with no request to our server, so nobody, including
// us, learns who added which shift to their calendar (PROJECT.md 2, 8.1).
import type { Listing } from "./types.ts";

export interface IcsText {
  /** The organization's own page for joining, and how to join, in the page's language. */
  description: string;
  /** Where, as shown on the page. */
  location: string;
}

/** Escapes a text value: backslash, semicolon, comma and line breaks. */
export function escapeText(value: string): string {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,")
    .replace(/\r?\n/g, "\\n");
}

/** Folds a content line at 75 bytes, as the standard asks. Never splits a character. */
export function foldLine(line: string): string {
  const encoder = new TextEncoder();
  const out: string[] = [];
  let current = "";
  let bytes = 0;
  for (const ch of line) {
    const size = encoder.encode(ch).length;
    const limit = out.length === 0 ? 75 : 74; // continuation lines start with a space
    if (bytes + size > limit) {
      out.push(current);
      current = "";
      bytes = 0;
    }
    current += ch;
    bytes += size;
  }
  out.push(current);
  return out.join("\r\n ");
}

/** 2026-10-20T18:00:00-04:00 to 20261020T220000Z */
export function utcStamp(iso: string): string {
  return new Date(iso).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}

export function buildIcs(e: Pick<Listing, "id" | "title" | "start" | "end" | "signup_url" | "last_seen_at">, text: IcsText): string {
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Citywide Volunteer Hub//Calendar site//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    `UID:${e.id}@citywide-volunteer-hub`,
    `DTSTAMP:${utcStamp(e.last_seen_at)}`,
    `DTSTART:${utcStamp(e.start)}`,
    ...(e.end ? [`DTEND:${utcStamp(e.end)}`] : []),
    `SUMMARY:${escapeText(e.title)}`,
    ...(text.location ? [`LOCATION:${escapeText(text.location)}`] : []),
    `DESCRIPTION:${escapeText(text.description)}`,
    `URL:${e.signup_url}`,
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  return lines.map(foldLine).join("\r\n") + "\r\n";
}
