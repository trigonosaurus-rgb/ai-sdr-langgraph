import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// The API runs separately (see tools/dev.mjs); Vite forwards /api to it, including SSE.
const api = process.env.SDR_API_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  // Keep the workspace URL stable for previews and example recordings.
  server: {
    port: Number(process.env.VITE_PORT ?? 5173),
    strictPort: true,
    proxy: { '/api': api },
  },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
