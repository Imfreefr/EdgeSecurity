import { defineConfig } from "vite";
import { cpSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
const projectRoot = fileURLToPath(new URL(".", import.meta.url));

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
        // Copy the validated ONNX model for browser inference (EdgeAILocal).
        // edgev1-int8.onnx is not a valid graph for the browser runtime.
        const modelSrc = resolve(projectRoot, "backend/model/edgev1.onnx");
        const modelDest = resolve(projectRoot, "dist/assets/edgev1.onnx");
        if (!existsSync(modelSrc)) throw new Error("Missing browser model: backend/model/edgev1.onnx");
        cpSync(modelSrc, modelDest);
        console.log("Copied edgev1.onnx to dist/assets/");
      },
    },
  ],
});
