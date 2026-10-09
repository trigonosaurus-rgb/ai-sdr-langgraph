# AI SDR workspace

React + TypeScript + Vite. A full-height Compose workspace, a separate Examples page, light/dark/system themes and a Run costs dialog. Generate starts a run on the FastAPI server and follows it live over SSE; the contract is in [INTEGRATION.md](INTEGRATION.md).

## Run on Windows

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev:all   # API on :8000 (with reload) and Vite on :5173
```

Open http://127.0.0.1:5173. Stop both with Ctrl+C. **Generate makes paid OpenAI and Tavily calls** with the keys from the root `.env`. `npm.cmd run dev` starts Vite alone; the workspace then reports the service as unavailable. `SDR_API_URL` points the `/api` proxy at another API. VS Code also has **Terminal → Run Task → Frontend: start preview**. Node 24 was used; dependencies are pinned. Fonts (Geist for the interface, Newsreader for the email) and video files are bundled locally.

## Interface

- Compose has three full-height columns: the brief, the draft (tabs for email, research and approach) and the run rail. The rail lists the stages vertically with per-stage durations, the latest activity, total time and estimated cost. Below 1280px the rail becomes a strip above the draft; below 960px the columns stack (brief, run, draft).
- Stage durations come from server-measured `elapsedMs` on events. The active stage shows a live clock that starts when its event arrives (after a reload, from the reload); finished timings are always the server's.
- Generate validates the brief with the server's rules and shows field errors on click instead of hiding the reason behind a disabled button. It is disabled only while the service is unreachable. During a run the brief is locked and the button becomes Cancel run; the status line under it reports the service, the run and lost connections. Limits and other refusals are shown as the server words them.
- `RunPanel` shows the draft as it streams, then makes it editable; copy and download are available only after a reviewed completion. A failure keeps partial output marked incomplete; a cancellation is shown neutrally, not as an error.
- Compose opens an empty brief, not a completed sample. Before a run, the draft area lists what a run produces; a shimmering outline appears only while a run is loading. The active run survives a reload: its brief is restored and its events are replayed from the server. New outreach clears the brief and the run (cancelling it if it is still going).
- Examples (`/#examples`) contains two real WebM recordings, with poster images and text walkthroughs. They autoplay silently when visible, loop and have a pause button. Offscreen/hidden videos stop. Reduced-motion preferences disable automatic playback; manual play remains available.
- Recordings replay real runs (Apollo in English, Kontur in Russian) from their stored events: stage times and costs are as measured, long waits are shortened and labelled so.
- Run costs opens a centered native dialog with a blurred backdrop and a detached close control. Escape, backdrop and the close button dismiss it. It loads usage from the server: this run (every call by step and draft, web search apart) or the visitor's runs over 24 hours or 30 days, plus the service's budget this month. Missing costs/tokens are shown as unknown, not zero, and incomplete totals are flagged; cache and reasoning are subsets of input/output.
- Motion (timeline fill, marker pop, active pulse, caret, content rise, status dot) is disabled under `prefers-reduced-motion`. Superelliptic corners use native CSS `corner-shape: squircle`, with rounded corners as a fallback.
- Styles use spacing, type and radius scales defined as custom properties at the top of `src/styles.css`.
- Old local sample drafts are intentionally not loaded into the real workspace. Run history beyond the active run is future work.

## Checks

```powershell
npm.cmd test
npm.cmd run test:browser
npm.cmd run build
npm.cmd run format:check
```

Browser checks use installed Microsoft Edge, with a fresh isolated test context. Playwright starts its own servers: the real API code on a scripted fake graph (`../tests/fake_server.py`, port 8765) and Vite on port 5174, so they never touch a dev server wired to paid providers. They cover a full streamed run, reload mid-run, cancel, a failed step, an invalid brief, an unreachable service, desktop/mobile layout, costs-dialog geometry, Escape/focus return, video playback/pause and reduced motion. DOM tests use a fake `EventSource` and `fetch` (`src/test/server.ts`): validation, starting, streaming, rejecting foreign and malformed events, reload recovery, cancel and refused starts. No external API calls are made. This does not constitute a full cross-browser or accessibility audit.

## Re-record examples

Videos are made from real runs, so re-recording costs nothing once a run is stored:

```powershell
npx.cmd playwright install ffmpeg
node tools/export-run.mjs <run-id> apollo        # from ../data/sdr.sqlite3 to tools/runs/apollo.json
npm.cmd run record:examples -- workflow=apollo evidence=kontur   # with Vite running on :5173
```

`tools/export-run.mjs` copies a finished run's brief and wire events, with each event's offset, from the local database. The development-only page `tools/capture.html` replays a fixture through the same `reduceRun`, `RunPanel` and `RunTimeline` as the app, with the server's stage times and costs; only waits over 1.2 s are shortened. The workflow scene plays the run from the start, the evidence scene opens on Research, scrolls the facts and shows the approach. The script takes frames straight from Chromium's screencast (JPEG at quality 100), resamples them to 25 fps and encodes VP8 once, by quality, with a single keyframe; Playwright's own recorder encodes in real time at 1 Mbit/s with periodic keyframes, which blurred text on scrolls and flashed a soft frame every few seconds. Output goes to `public/examples/*.webm`, with posters. `BROWSER_CHANNEL` can select another installed Chromium channel; the default is `msedge`. Temporary recordings are ignored by Git; the capture page is not in the production bundle. Fixtures are public data (brief, facts, draft): check a run for private data before exporting it.

## Main files

- `src/App.tsx`: shell, Compose/Examples navigation, dialog state and the status line.
- `src/api.ts`: API requests with readable errors, brief validation, runtime event validation and the SSE follower.
- `src/useRun.ts`: run lifecycle — start, cancel, reload recovery, service status.
- `src/components/BriefForm.tsx`: brief form with field errors, Generate/Cancel and the status line.
- `src/components/RunPanel.tsx`: draft column with tabs, editor and empty states.
- `src/components/RunTimeline.tsx`: run rail with stage timings, live clock, activity and totals.
- `src/run.ts`: event contract, reducer and `stageDurations`.
- `src/components/Examples.tsx`: video visibility, playback and reduced-motion behavior.
- `src/components/Metrics.tsx`: Run costs; fetches usage by period and shows nullable token counts and cost estimates.
- `src/components/Modal.tsx`: native dialog, scroll lock and focus restoration.
- `tools/dev.mjs`: `npm run dev:all`, the API and Vite together.
- `tools/record-examples.mjs`: reproducible video recording.

The frontend needs no `.env` or API keys: Vite's root is this directory and does not load the Python project's `.env`. Provider keys remain on the server.
