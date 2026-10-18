// robots.txt. A test build (PV_TEST_BUILD=1) asks every search engine to stay
// out (decision 0009); a normal build lets them in.
import type { APIRoute } from "astro";
import { siteData } from "../lib/site.ts";

export const GET: APIRoute = () => {
  const body = siteData().testBuild ? "User-agent: *\nDisallow: /\n" : "User-agent: *\nAllow: /\n";
  return new Response(body, { headers: { "Content-Type": "text/plain; charset=utf-8" } });
};
