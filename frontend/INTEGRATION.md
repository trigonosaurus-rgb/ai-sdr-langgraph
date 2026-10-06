# Next integration contract

This document records requirements, not implemented backend functionality.

## Live workflow

`src/run.ts` is a view-state prototype. Feed it validated events from the active server-issued run, carrying `runId` and monotonically increasing `sequence`. Events describe public work (search, source collection, writing, review), not private chain-of-thought. Deliver draft chunks with `draft_delta`. Do not infer successful completion from the connection closing or from having text: the server must issue an explicit reviewed completion. Keep partial output visibly incomplete on failure.

Before connecting the API, add runtime validation, resume/reconnect with ordered event replay, cancellation acknowledged by the server, retry snapshots that replace the previous draft, and persisted run recovery after reload. The transport must reject stale `started` events from unrelated runs; the reducer alone is not a network boundary. Current events are an internal UI contract, not yet an SSE or WebSocket client.

Replace `emptyRun` in App with server state; enable Generate only when the service is available and the brief passes validation. Model/search usage is reported by the server, including unsuccessful paid attempts. Extend `RunUsage` to per-call/attempt breakdown, pricing version and daily history before implementing the full roadmap metrics.

## Access and three real trials

- Anonymous visitor: Examples remains accessible; sign in to use three trial runs. Do not show an invented remaining balance.
- Authenticated account: server returns `access: allowed | trial | exhausted`, `trialLimit: 3`, and authoritative `remaining`. Display “3 of 3 trial runs left” (then 2, 1, 0) near Generate and in the sidebar.
- Allowlisted/paid users can generate. Exhausted users see “Your three trial runs are used. Get access to continue,” with an actual purchase/contact destination once the owner chooses a payment flow. There is no checkout in this iteration.
- Enforce access and quota on every server endpoint. Atomically reserve a trial with an idempotent run creation request; parallel clicks and reconnects must not consume or exceed the quota twice. Never trust localStorage or a client counter.
- Proposed policy for agreement during backend work: release the reservation for validation/provider failure before a useful result; consume on a completed reviewed result. Separately cap retries, failed requests and daily cost to prevent unlimited paid failures. Record provider spend even when a trial is refunded.
- MIT permits charging for hosted access. Keep license/copyright notices on distributed copies and inspect dependency obligations. Open code does not grant use of the hosted service, your provider keys or an unlimited compute budget.

Auth and billing are separate from research quality; implement trial accounting in stage 4 and the purchase flow before public paid access in stage 6.
