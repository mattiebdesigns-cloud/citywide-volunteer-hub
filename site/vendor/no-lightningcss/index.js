// Stand-in for "lightningcss". See package.json.
// Vite loads this file when it starts but, with the settings in
// astro.config.mjs, never calls it. Any call stops the build with a plain error.
const notInstalled = (name) => () => {
  throw new Error(
    `lightningcss.${name} was called, but lightningcss is not installed (MPL-2.0 is not allowed). ` +
      "Keep vite.css.transformer 'postcss' and vite.build.cssMinify false in astro.config.mjs (see site/README.md).",
  );
};
module.exports = new Proxy({}, { get: (_, name) => (name === "__esModule" ? false : notInstalled(String(name))) });
