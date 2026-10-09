// Exports one stored run as a recording fixture: the brief and every wire event with its offset
// from the first one, as the server stored them. tools/capture.tsx replays it for the Examples videos.
//   node tools/export-run.mjs <run-id> <name>   ->  tools/runs/<name>.json
// Reads the local API database (SDR_DB_PATH or ../data/sdr.sqlite3). No network, no cost.
import { DatabaseSync } from 'node:sqlite'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const [runId, name] = process.argv.slice(2)
if (!runId || !/^[\w-]+$/.test(name ?? '')) {
  console.error('Usage: node tools/export-run.mjs <run-id> <name>')
  process.exit(1)
}
const database = path.resolve(
  process.env.SDR_DB_PATH ?? path.join('..', 'data', 'sdr.sqlite3'),
)
const db = new DatabaseSync(database, { readOnly: true })
const run = db
  .prepare('SELECT id, status, brief, created_at FROM runs WHERE id = ?')
  .get(runId)
if (!run) throw new Error(`No run ${runId} in ${database}`)
if (run.status === 'running') throw new Error('The run has not finished yet')
const rows = db
  .prepare(
    'SELECT data, created_at FROM events WHERE run_id = ? ORDER BY sequence',
  )
  .all(runId)
const start = Date.parse(rows[0].created_at)
const fixture = {
  runId: run.id,
  status: run.status,
  recordedAt: run.created_at,
  brief: JSON.parse(run.brief),
  events: rows.map((row) => ({
    atMs: Date.parse(row.created_at) - start,
    event: JSON.parse(row.data),
  })),
}
const directory = path.resolve('tools', 'runs')
await mkdir(directory, { recursive: true })
const output = path.join(directory, `${name}.json`)
await writeFile(output, JSON.stringify(fixture, null, 2) + '\n')
console.log(
  `Exported ${rows.length} events of a ${run.status} run (${(fixture.events.at(-1).atMs / 1000).toFixed(1)} s) to ${path.relative('.', output)}`,
)
