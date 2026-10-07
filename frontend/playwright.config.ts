import path from 'node:path'
import { defineConfig } from '@playwright/test'

// Browser tests run against the real API code on a scripted fake graph (tests/fake_server.py),
// on their own ports, so they never reach a dev server wired to paid providers.
// Forward slashes and quotes: the command string is split shell-style, even on Windows.
const python = JSON.stringify(
  path
    .resolve(
      import.meta.dirname,
      '..',
      '.venv',
      process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
    )
    .split(path.sep)
    .join('/'),
)
const apiPort = 8765
const webPort = 5174

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    channel: 'msedge',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: `${python} -m uvicorn tests.fake_server:app --port ${apiPort}`,
      cwd: '..',
      url: `http://127.0.0.1:${apiPort}/api/health`,
      reuseExistingServer: false,
    },
    {
      command: 'npm run dev',
      url: `http://127.0.0.1:${webPort}`,
      reuseExistingServer: false,
      env: {
        VITE_PORT: String(webPort),
        SDR_API_URL: `http://127.0.0.1:${apiPort}`,
      },
    },
  ],
})
