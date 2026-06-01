import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    lib: {
      entry: 'src/plugin-entry.tsx',
      name: 'SystemMonitorPlugin',
      fileName: 'index',
      formats: ['iife'],
    },
    rollupOptions: {
      external: ['react', 'react-dom', 'react/jsx-runtime'],
      output: {
        globals: {
          react: 'React',
          'react-dom': 'ReactDOM',
          'react/jsx-runtime': 'jsxRuntime',
        },
      },
    },
  },
});
