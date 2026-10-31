// Stand-in for "lightningcss". See package.json.
// Vite loads this file when it starts but, with the settings in
// astro.config.mjs, never calls it. Any call stops the build with a plain error.
const notInstalled = (name) => () => {
  throw new Error(
    `lightningcss.${name} was called, but lightningcss is not installed (MPL-2.0 is not allowed). ` +
      "Keep vite.css.transformer 'postcss' and vite.build.cssMinify false in astro.config.mjs (see site/README.md).",
  );
};
// Vite loads this file with import(), and Node finds a CommonJS file's named
// exports only when they are written out one by one like this. Without them,
// a call would fail with "transform is not a function" instead of the message above.
exports.transform = notInstalled("transform");
exports.transformStyleAttribute = notInstalled("transformStyleAttribute");
exports.bundle = notInstalled("bundle");
exports.bundleAsync = notInstalled("bundleAsync");
exports.browserslistToTargets = notInstalled("browserslistToTargets");
exports.composeVisitors = notInstalled("composeVisitors");
// Any other name, read the CommonJS way (require), gives the same error.
module.exports = new Proxy(exports, {
  get: (target, name) => (name === "__esModule" ? false : name in target ? target[name] : notInstalled(String(name))),
});
