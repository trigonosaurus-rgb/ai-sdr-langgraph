# API contract

The workspace talks to the FastAPI server in `../server/` through the `/api` proxy (see `vite.config.ts`). Provider keys stay on the server.

## Endpoints

| Request                             | Response                                                                                                                                                                                        |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/health`                   | `{status: "ok"}`; Generate is enabled only while this succeeds (rechecked every 15 s when it fails)                                                                                             |
| `POST /api/runs` with the brief     | `201 {runId}`; `422` with field errors; `429` with a readable `detail` (one run at a time per address, hourly limit) and `Retry-After` when waiting helps                                       |
| `GET /api/runs/{id}/events?after=N` | SSE: stored events with `sequence > N` (or > `Last-Event-ID` on an automatic reconnect), then live ones; each SSE `id` is the event's `sequence`. The stream ends after `completed` or `failed` |
| `POST /api/runs/{id}/cancel`        | `202` accepted, `409` if the run is not running. The stream confirms with `failed` and reason `cancelled`, or with the normal outcome if the last paid call had already finished                |
| `GET /api/runs/{id}`                | `{runId, status, reason, brief, createdAt, finishedAt, lastSequence}`; `404` for unknown runs                                                                                                   |

## Events

`src/run.ts` declares the event union and `reduceRun`; `core/events.py` mirrors it, and `tests/test_events.py` fails if event types or `FailureReason` values drift apart. `src/api.ts` validates every event's shape at runtime and drops events from other runs before they reach the reducer.

- A run begins with `started`; only `started` can switch the view to another run.
- `draft_reset` starts each attempt (and repairs a stream that diverged from the final text); `draft_delta` chunks concatenate to the reviewed draft exactly.
- Completion is explicit: `completed` (`ready` or `needs_attention`, with `issues` and `usage`) or `failed` (`insufficient_data`, `website_mismatch`, `cancelled`, `error`). A closed connection or existing text never means success. Partial output stays visibly incomplete on failure.
- `elapsedMs` is measured by the server from the run start, so stage timings survive reconnects.
- Unknown usage is `null`, never zero. Cost fields stay `null` until pricing lands in stage 4.

## Reload recovery

The active run id is kept in `localStorage` (`ai-sdr.active-run.v1`) until New outreach. On load the app fetches the snapshot, restores the brief and replays the run's events from the start, so a finished run shows its result again. A `404` forgets the id.

## Access

Decided 2026-10-07: the public version is open without accounts, protected by server-side limits (runs per hour per address, one concurrent run per address) and a service-wide daily cost ceiling checked before each paid call (stage 4). Accounts, trial counters and payments are out of scope; see ROADMAP.md. Never trust a client-side counter.

- MIT permits hosting the service. Keep license/copyright notices on distributed copies and inspect dependency obligations. Open code does not grant use of the hosted service, your provider keys or an unlimited compute budget.
