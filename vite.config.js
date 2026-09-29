import { defineConfig } from "vite";
import { cpSync } from "node:fs";
// Only the landing enters Vite. Internal pages retain their original assets.
export default defineConfig({
  publicDir: false,
  build: { rollupOptions: { input: "landing.html" } },
  plugins: [
    {
      name: "preserve-legacy-pages",
      closeBundle() {
        for (const path of ["index.html", "pages", "css", "js", "assets"]) {
          cpSync(path, `dist/${path}`, { recursive: true });
        }
      },
    },
  ],
});
