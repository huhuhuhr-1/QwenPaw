import { defineConfig } from "vite";

export default defineConfig({
  esbuild: {
    jsxFactory: "React.createElement",
    jsxFragment: "React.Fragment",
  },
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
  },
  build: {
    lib: {
      entry: "src/plugin-entry.tsx",
      name: "SystemMonitorPlugin",
      formats: ["iife"],
      fileName: () => "index.iife.js",
    },
    rollupOptions: {
      external: ["react", "react-dom"],
      output: {
        globals: {
          react: "window.React",
          "react-dom": "window.ReactDOM",
        },
        inlineDynamicImports: true,
      },
    },
    minify: false,
    sourcemap: true,
    outDir: "dist",
  },
});
