import { defineConfig } from "vite";
import { resolve } from "path";

export default defineConfig({
  resolve: {
    alias: { "@": resolve(__dirname, "src") },
  },
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
  },
  build: {
    lib: {
      entry: resolve(__dirname, "src/plugin-entry.ts"),
      name: "GitHubTrending",
      formats: ["iife"],
      fileName: () => "index.js",
    },
    rollupOptions: {
      external: [],
      output: {
        inlineDynamicImports: true,
      },
    },
    minify: false,
    sourcemap: true,
    outDir: "dist",
  },
});
