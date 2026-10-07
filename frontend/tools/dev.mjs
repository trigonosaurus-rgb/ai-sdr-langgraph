// One command for local development: the FastAPI server (with reload) and Vite.
// Generate in this setup makes PAID OpenAI and Tavily calls with the keys from ../.env.
// Stop both with Ctrl+C.
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const frontend = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..',
)
const root = path.resolve(frontend, '..')
const python = [
  path.join(root, '.venv', 'Scripts', 'python.exe'),
  path.join(root, '.venv', 'bin', 'python'),
].find(existsSync)
if (!python) {
  console.error('No .venv found in the project root. See README.md, Setup.')
  process.exit(1)
}
const port = process.env.SDR_API_PORT ?? '8000'
const windows = process.platform === 'win32'

const children = [
  spawn(
    python,
    [
      '-m',
      'uvicorn',
      'server.app:app',
      '--port',
      port,
      '--reload',
      '--reload-dir',
      'core',
      '--reload-dir',
      'agents',
      '--reload-dir',
      'server',
      '--reload-dir',
      'prompts',
    ],
    { cwd: root, stdio: 'inherit' },
  ),
  spawn(windows ? 'npm.cmd' : 'npm', ['run', 'dev'], {
    cwd: frontend,
    stdio: 'inherit',
    shell: windows, // npm.cmd needs a shell on Windows
    env: { ...process.env, SDR_API_URL: `http://127.0.0.1:${port}` },
  }),
]

let stopping = false
function stop(code = 0) {
  if (stopping) return
  stopping = true
  for (const child of children) {
    if (child.exitCode !== null) continue
    if (windows)
      spawn('taskkill', ['/pid', String(child.pid), '/t', '/f'], {
        stdio: 'ignore',
      })
    else child.kill('SIGINT')
  }
  process.exitCode = code
}
for (const child of children) child.on('exit', (code) => stop(code ?? 0))
process.on('SIGINT', () => stop(0))
process.on('SIGTERM', () => stop(0))
