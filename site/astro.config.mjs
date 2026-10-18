// Calendar site build settings (PROJECT.md sections 2 and 3).
//
// Build-time inputs, all optional:
//   PV_EVENTS      path to the events file   (default: ../docs/examples/events.sample.json)
//   PV_SETTINGS    path to the city settings (default: settings.example.json)
//   PV_SITE_URL    the site's public address, e.g. https://example.org (used for full links)
//   PV_TEST_BUILD  1 for a test build: "Test version" line, noindex, robots.txt blocks everything
// Relative paths are read from the folder you run the command in.
import { defineConfig, passthroughImageService } from "astro/config";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

const here = fileURLToPath(new URL(".", import.meta.url));
const fromCwd = (p) => resolve(process.cwd(), p);

process.env.PV_EVENTS_PATH = process.env.PV_EVENTS
  ? fromCwd(process.env.PV_EVENTS)
  : resolve(here, "../docs/examples/events.sample.json");
process.env.PV_SETTINGS_PATH = process.env.PV_SETTINGS
  ? fromCwd(process.env.PV_SETTINGS)
  : resolve(here, "settings.example.json");

export default defineConfig({
  site: process.env.PV_SITE_URL || undefined,
  output: "static",
  trailingSlash: "ignore",
  build: { format: "directory" },
  // No image processing, so the LGPL image library is never needed (see vendor/no-sharp).
  image: { service: passthroughImageService() },
  devToolbar: { enabled: false },
});
