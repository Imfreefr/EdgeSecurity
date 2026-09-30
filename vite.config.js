import { defineConfig } from "vite";
import { cpSync, existsSync } from "node:fs";
import { resolve } from "node:path";

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
        // Copy ONNX model for browser inference (EdgeAILocal)
        const modelSrc = resolve(__dirname, "backend/model/edgev1-int8.onnx");
        const modelDest = resolve(__dirname, "dist/assets/edgev1-int8.onnx");
        if (existsSync(modelSrc)) {
          cpSync(modelSrc, modelDest);
          console.log("Copied edgev1-int8.onnx to dist/assets/");
        }
      },
    },
  ],
});
