// Small line icons, drawn for this project (MIT, like the rest of the repo).
// Used by Icon.astro. Each entry is the inside of a 24 x 24 drawing.

export type IconName =
  | "heart"
  | "share"
  | "clock"
  | "pin"
  | "walk-in"
  | "signup"
  | "apply"
  | "question"
  | "service"
  | "training"
  | "campaign"
  | "protest_action"
  | "full"
  | "spots"
  | "business"
  | "external"
  | "sensitive"
  | "calendar"
  | "check"
  | "close"
  | "filter"
  | "globe"
  | "flag"
  | "info";

// Stroked with currentColor, so an icon takes the colour of the text next to it.
export const paths: Record<IconName, string> = {
  heart:
    '<path d="M12 20.5s-7.5-4.6-7.5-10.3A4.2 4.2 0 0 1 12 7.6a4.2 4.2 0 0 1 7.5 2.6c0 5.7-7.5 10.3-7.5 10.3Z"/>',
  share:
    '<path d="M12 3.5v11"/><path d="m7.5 8 4.5-4.5L16.5 8"/><path d="M5 12.5v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  pin: '<path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.3"/>',
  "walk-in": '<path d="M5 20.5V4.5h10v16"/><path d="M15 20.5h4"/><path d="M3 20.5h2"/><circle cx="12" cy="12.5" r="0.9" fill="currentColor"/><path d="M15 4.5l4 2v14"/>',
  signup: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V2.8h6V4"/><path d="m8.5 13 2.3 2.3 4.7-4.8"/>',
  apply: '<path d="M6 3.5h8l4 4v13H6z"/><path d="M14 3.5v4h4"/><path d="M9 12h6M9 15.5h6M9 19h3.5"/>',
  question:
    '<circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.6a2.5 2.5 0 1 1 3.4 2.3c-.7.3-1 .8-1 1.5v.6"/><circle cx="12" cy="16.9" r="0.6" fill="currentColor"/>',
  service: '<path d="M3.5 13.5h3l3.5 3h4.5a1.5 1.5 0 0 0 0-3H11"/><path d="M6.5 19.5h8.2l5.8-4a1.5 1.5 0 0 0-1.8-2.4L15.5 15"/><path d="M14.5 9.6S11.5 8 11.5 6a1.6 1.6 0 0 1 3-.8 1.6 1.6 0 0 1 3 .8c0 2-3 3.6-3 3.6Z"/>',
  training: '<path d="M2.5 9 12 4.5 21.5 9 12 13.5z"/><path d="M6.5 11v4.5c1.5 1.5 3.4 2.2 5.5 2.2s4-.7 5.5-2.2V11"/><path d="M21.5 9v5.5"/>',
  campaign: '<rect x="4" y="10.5" width="16" height="10" rx="1.5"/><path d="M8.5 10.5 10 4.5h6.5l-1.5 6"/><path d="M9 15.5h6"/>',
  protest_action: '<path d="M4 10v4l3 .5"/><path d="M7 9.5 17.5 5v14L7 14.5z"/><path d="M8.5 15l1.2 4.5h2.6l-1-4"/><path d="M20 10.5v3"/>',
  full: '<circle cx="12" cy="12" r="8.5"/><path d="m6 6 12 12"/>',
  spots: '<path d="M4 7.5h16v3a1.8 1.8 0 0 0 0 3.5v3H4v-3a1.8 1.8 0 0 0 0-3.5z"/><path d="M14.5 7.5v9.5" stroke-dasharray="1.6 1.6"/>',
  business: '<rect x="3.5" y="7.5" width="17" height="12" rx="1.8"/><path d="M9 7.5V5.5h6v2"/><path d="M3.5 12.5h17"/><path d="M11 12.5v1.5h2v-1.5"/>',
  external: '<path d="M13.5 4.5h6v6"/><path d="M19.5 4.5 11 13"/><path d="M17 14v4.5a1.5 1.5 0 0 1-1.5 1.5h-10A1.5 1.5 0 0 1 4 18.5v-10A1.5 1.5 0 0 1 5.5 7H10"/>',
  sensitive: '<path d="M12 3 5 5.8v5.4c0 4.3 3 7.9 7 9.3 4-1.4 7-5 7-9.3V5.8z"/><path d="M12 8.5v4.5"/><circle cx="12" cy="16" r="0.6" fill="currentColor"/>',
  calendar: '<rect x="4" y="5.5" width="16" height="15" rx="2"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  filter: '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
  globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17"/><path d="M12 3.5c2.3 2.4 3.4 5.2 3.4 8.5s-1.1 6.1-3.4 8.5c-2.3-2.4-3.4-5.2-3.4-8.5S9.7 5.9 12 3.5Z"/>',
  flag: '<path d="M5.5 21V4"/><path d="M5.5 4.5h11l-2 4 2 4h-11"/>',
  info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5"/><circle cx="12" cy="7.8" r="0.6" fill="currentColor"/>',
};
