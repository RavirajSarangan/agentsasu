import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    target: "es2022",
    rollupOptions: { input: { main: resolve(__dirname, "index.html"), dmg: resolve(__dirname, "dmg.html"), og: resolve(__dirname, "og.html"), compare: resolve(__dirname, "compare.html"), privacy: resolve(__dirname, "privacy.html"), terms: resolve(__dirname, "terms.html"), banner: resolve(__dirname, "banner.html") } },
  },
});
