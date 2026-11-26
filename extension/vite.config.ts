import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        sidepanel: fileURLToPath(new URL('./sidepanel/index.html', import.meta.url)),
        'service-worker': fileURLToPath(
          new URL('./src/background/serviceWorker.ts', import.meta.url),
        ),
      },
      output: {
        entryFileNames: (chunkInfo) =>
          chunkInfo.name === 'service-worker'
            ? 'service-worker.js'
            : 'assets/[name]-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
      },
    },
  },
  test: {
    environment: 'node',
  },
})
