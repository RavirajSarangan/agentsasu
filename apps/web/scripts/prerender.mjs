// After `vite build`: render the landing page to HTML and put it inside #root.
import { readFile, rm, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { build } from "vite";

const root = resolve(import.meta.dirname, "..");
const out = resolve(root, "node_modules/.prerender");
await build({
  root,
  logLevel: "warn",
  build: { ssr: "src/entry-server.tsx", outDir: out, emptyOutDir: true, rollupOptions: { input: "src/entry-server.tsx" } },
});
const { render } = await import(pathToFileURL(resolve(out, "entry-server.js")).href);
const html = render();
const page = resolve(root, "dist/index.html");
const doc = await readFile(page, "utf8");
if (!doc.includes('<div id="root"></div>')) throw new Error("dist/index.html has no empty #root");
let out_ = doc.replace('<div id="root"></div>', `<div id="root">${html}</div>`);
// The landing page is pre-rendered, so its CSS is the only thing between the HTML and the
// first paint: inline it (≈10 KB compressed) instead of waiting for another request.
const link = out_.match(/<link rel="stylesheet" crossorigin href="(\/assets\/[^"]+\.css)">/);
if (link) {
  const css = await readFile(resolve(root, "dist", link[1].slice(1)), "utf8");
  out_ = out_.replace(link[0], `<style>${css.replaceAll("</style", "<\\/style")}</style>`);
}
// The two Latin fonts the first screen uses: start them with the HTML, not after the CSS.
const fonts = [...css_fonts(out_)].map((f) => `<link rel="preload" as="font" type="font/woff2" crossorigin href="${f}">`).join("");
out_ = out_.replace("</title>", `</title>${fonts}`);
await writeFile(page, out_);
await rm(out, { recursive: true, force: true });
function* css_fonts(doc) {
  for (const name of ["bricolage-grotesque-latin-wght-normal", "instrument-sans-latin-wght-normal"]) {
    const m = doc.match(new RegExp(`/assets/${name}-[\\w-]+\\.woff2`));
    if (m) yield m[0];
  }
}
console.log(`prerendered index.html (${Math.round(html.length / 1024)} KB of HTML)`);
