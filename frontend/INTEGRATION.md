# Next integration contract

This document records requirements, not implemented backend functionality.

## Live workflow

`src/run.ts` is a view-state prototype. Its event union is mirrored by `core/events.py`, and `tests/test_events.py` fails if the two sets of event types drift apart. A rewrite starts with `draft_reset`, which replaces the previous draft; `completed` carries `outcome` (`ready` or `needs_attention`) and `issues`; `failed` carries `reason` (`insufficient_data`, `website_mismatch` or `error`). The detailed presentation of strategy hypotheses, review issues and `needs_attention` is still minimal and is designed in stage 3. Feed it validated events from the active server-issued run, carrying `runId` and monotonically increasing `sequence`. Events describe public work (search, source collection, writing, review), not private chain-of-thought. Deliver draft chunks with `draft_delta`. Do not infer successful completion from the connection closing or from having text: the server must issue an explicit reviewed completion. Keep partial output visibly incomplete on failure.

Before connecting the API, add runtime validation, resume/reconnect with ordered event replay, cancellation acknowledged by the server, retry snapshots that replace the previous draft, and persisted run recovery after reload. The transport must reject stale `started` events from unrelated runs; the reducer alone is not a network boundary. Current events are an internal UI contract, not yet an SSE or WebSocket client.

Replace `emptyRun` in App with server state; enable Generate only when the service is available and the brief passes validation. Model/search usage is reported by the server, including unsuccessful paid attempts. Extend `RunUsage` to per-call/attempt breakdown, pricing version and daily history before implementing the full roadmap metrics.

## Access

Decided 2026-10-07: the public version is open without accounts, protected by server-side limits (runs per hour per address, one concurrent run per address) and a service-wide daily cost ceiling checked before each paid call. Accounts, trial counters and payments are out of scope; see ROADMAP.md. Never trust a client-side counter.

- MIT permits hosting the service. Keep license/copyright notices on distributed copies and inspect dependency obligations. Open code does not grant use of the hosted service, your provider keys or an unlimited compute budget.
