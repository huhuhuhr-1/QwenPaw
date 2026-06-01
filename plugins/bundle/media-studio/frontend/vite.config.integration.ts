import { defineConfig } from "vite";

export default defineConfig({
  build: {
    lib: {
      entry: "src/plugin-entry.ts",
      name: "MediaStudioPlugin",
      fileName: () => "index.js",
      formats: ["iife"],
    },
    rollupOptions: {
      external: [],
      output: {
        globals: {},
      },
    },
  },
});
