// Loads every `<code>.json` in this folder. Astro (Vite) resolves the glob at
// build time, so a new language file is picked up with no code change.
import type { Messages } from "./index";

const files = import.meta.glob<Messages>("./*.json", { eager: true, import: "default" });

export const catalogs: Record<string, Messages> = Object.fromEntries(
  Object.entries(files).map(([path, messages]) => [path.replace(/^.*\/|\.json$/g, ""), messages]),
);
