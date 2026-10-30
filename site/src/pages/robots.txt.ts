// robots.txt (decision 0009, changed by 0014). A test build (PV_TEST_BUILD=1)
// lets in only Facebook's link-preview bot; every other crawler stays out. A
// normal build lets them all in. The text comes from src/lib/og.ts.
import type { APIRoute } from "astro";
import { robotsTxt } from "../lib/og.ts";
import { siteData } from "../lib/site.ts";

export const GET: APIRoute = () =>
  new Response(robotsTxt(siteData().testBuild), { headers: { "Content-Type": "text/plain; charset=utf-8" } });
