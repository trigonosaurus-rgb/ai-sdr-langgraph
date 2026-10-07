# API contract

The workspace talks to the FastAPI server in `../server/` through the `/api` proxy (see `vite.config.ts`). Provider keys stay on the server.

## Endpoints

| Request                             | Response                                                                                                                                                                                                                                                                          |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/health`                   | `{status: "ok"}` for infrastructure checks                                                                                                                                                                                                                                        |
| `GET /api/status`                   | `{paused, developer, visitor}`: whether the service is stopped for visitors, whether the caller is the developer, and the caller's quota. Generate is enabled only while this succeeds and allows a run (rechecked every 15 s when it fails, and after each run or refused start) |
| `POST /api/runs` with the brief     | `201 {runId}`; `422` with field errors; `429` with a readable `detail` (one run at a time per address, the visitor quota, the service stopped by the developer) and `Retry-After` when waiting helps                                                                              |
| `GET /api/runs/{id}/events?after=N` | SSE: stored events with `sequence > N` (or > `Last-Event-ID` on an automatic reconnect), then live ones; each SSE `id` is the event's `sequence`. The stream ends after `completed` or `failed`                                                                                   |
| `POST /api/runs/{id}/cancel`        | `202` accepted, `409` if the run is not running. The stream confirms with `failed` and reason `cancelled`, or with the normal outcome if the last paid call had already finished                                                                                                  |
| `GET /api/runs/{id}`                | `{runId, status, reason, brief, createdAt, finishedAt, lastSequence}`; `404` for unknown runs                                                                                                                                                                                     |
| `GET /api/runs/{id}/usage`          | `{runId, status, totals, llmCalls, searchCalls}`: every paid call of the run, failed ones included, in order. Grows while the run is in progress                                                                                                                                  |
| `GET /api/usage?period=24h\|30d`    | `{period, since, totals, budget}`: the caller's runs started within the period, and the service's spending this month against its budget                                                                                                                                          |

## Events

`src/run.ts` declares the event union and `reduceRun`; `core/events.py` mirrors it, and `tests/test_events.py` fails if event types or `FailureReason` values drift apart. `src/api.ts` validates every event's shape at runtime and drops events from other runs before they reach the reducer.

- A run begins with `started`; only `started` can switch the view to another run.
- `draft_reset` starts each attempt (and repairs a stream that diverged from the final text); `draft_delta` chunks concatenate to the reviewed draft exactly.
- Completion is explicit: `completed` (`ready` or `needs_attention`, with `issues` and `usage`) or `failed` (`insufficient_data`, `website_mismatch`, `cancelled`, `budget_exhausted`, `error`). A closed connection or existing text never means success. Partial output stays visibly incomplete on failure.
- `elapsedMs` is measured by the server from the run start, so stage timings survive reconnects.
- Unknown usage is `null`, never zero.

## Usage and costs

- Each paid call's cost is computed when the call is recorded, from the dated price table in `core/pricing.py`, and stored with its version. It is never recomputed; calls stored before pricing keep an unknown cost.
- `totals` (`UsageTotals` in `server/store.py`) sums what the calls reported. A total is `null` when calls exist but none reported it; `incomplete` is set when some did not. Zero means zero, e.g. no runs.
- Cached input is a subset of input and reasoning a subset of output: priced once, never added twice.
- Web search is priced at the Tavily pay-as-you-go rate per credit, even on the free plan, so the estimate shows the real cost of a run.

## Reload recovery

The active run id is kept in `localStorage` (`ai-sdr.active-run.v1`) until New outreach. On load the app fetches the snapshot, restores the brief and replays the run's events from the start, so a finished run shows its result again. A `404` forgets the id.

## Access

Decided 2026-10-07: the public version is open without accounts, protected by server-side limits. Per address (hashed): one run at a time, 3 runs in 24 hours and 10 in 30 days (`SDR_RUNS_PER_DAY`, `SDR_RUNS_PER_MONTH`); a device cannot be identified without accounts, and a browser-side id is reset by a private window, so the address is the limit. Service-wide, per calendar month in UTC (Tavily's free credits reset on the 1st): $5 of model spending (`SDR_MONTHLY_MODEL_USD`) and 750 search credits (`SDR_MONTHLY_SEARCH_CREDITS`). A new run starts only if it fits with a reserve for every run in progress; each paid call is checked again, and a run that hits the limit ends `failed` with reason `budget_exhausted`. While the budget is used up the workspace shows a large "Service temporarily stopped by the developer" notice, with no date: the developer decides when it is back (the counters themselves start over on the 1st).

The developer has no limits: set `SDR_DEVELOPER_KEY` on the server and open the site once with `/#developer=<key>`. The fragment never reaches the server; the app keeps the key in `localStorage` (`ai-sdr.developer-key.v1`), removes it from the address and sends it as `X-Developer-Key`. `/#developer=` forgets it. Quota, pause, one-run-at-a-time and the budget checks before paid calls do not apply; the developer's spending still counts toward the budget. Accounts, trial counters and payments are out of scope; see ROADMAP.md. Never trust a client-side counter.

- MIT permits hosting the service. Keep license/copyright notices on distributed copies and inspect dependency obligations. Open code does not grant use of the hosted service, your provider keys or an unlimited compute budget.
