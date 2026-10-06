# AI SDR workspace

React + TypeScript + Vite. One Compose screen, a separate Examples page, light/dark/system themes and a Run costs dialog. **The Python graph is not connected yet:** generation is disabled with an explanation. No model calls or trial runs are made by this frontend.

## Run on Windows

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open http://127.0.0.1:5173. Stop with Ctrl+C. If this port already serves the app, reuse it. VS Code also has **Terminal → Run Task → Frontend: start preview**. Node 24 was used; dependencies are pinned. Fonts and video files are local.

## Interface

- Compose opens an empty brief, not a completed sample. The form stays intact when visiting Examples, but is not persisted across reloads. New outreach clears it.
- Examples (`/#examples`) contains two real WebM recordings, with poster images and text walkthroughs. They autoplay silently when visible, loop and have a pause button. Offscreen/hidden videos stop. Reduced-motion preferences disable automatic playback; manual play remains available.
- Recordings use fictional Northstar data and are labelled illustrative. Incremental writing demonstrates the future streaming UI, not a live model response.
- Run costs opens a centered native dialog with a blurred backdrop and a detached close control. Escape, backdrop and the close button dismiss it. Missing costs/tokens are shown as unknown, not zero; cache and reasoning are subsets of input/output.
- The result, from Run status to the review reminder, shares one continuous panel. Superelliptic corners use native CSS `corner-shape: squircle`, with rounded corners as a fallback.
- `RunPanel` can display partial drafts, activity messages, evidence, errors and editable completed drafts. Copy and download are available only after completion. It is not wired to a backend transport.
- Old local sample drafts are intentionally not loaded into the real workspace. Backend history and draft persistence remain future work.

## Checks

```powershell
npm.cmd test
npm.cmd run test:browser
npm.cmd run build
npm.cmd run format:check
```

Browser checks use installed Microsoft Edge, with a fresh isolated test context. They check desktop/mobile layout, costs-dialog geometry, Escape/focus return, video playback/pause, reduced motion and brief preservation. DOM tests cover missing usage, draft editing/copying and theme settings. Stream-state tests cover duplicate events, foreign run events and errors after partial output. No external API calls are made. This does not constitute a full cross-browser or accessibility audit.

## Re-record examples

Keep Vite running, then:

```powershell
npx.cmd playwright install ffmpeg
npm.cmd run record:examples
```

The development-only page `tools/capture.html` renders the same `RunPanel` as the app. `tools/fixtures.ts` and its timed events provide explicitly fictional material. The script records with Playwright into `public/examples/*.webm` and captures posters. `BROWSER_CHANNEL` can select another installed Chromium channel; the default is `msedge`. Temporary recordings are ignored by Git. Neither the capture entry nor fixtures are in the production JS bundle. When real streaming is connected, replace these recordings with captured live runs, reviewing them for private data before publishing.

## Main files

- `src/App.tsx`: shell, Compose/Examples navigation and dialog state.
- `src/components/BriefForm.tsx`: real-workflow brief form, currently disconnected.
- `src/components/RunPanel.tsx`: shared result, activity and incremental draft UI.
- `src/run.ts`: proposed view-state event contract and reducer, **not** a final API schema.
- `src/components/Examples.tsx`: video visibility, playback and reduced-motion behavior.
- `src/components/Metrics.tsx`: display of nullable token counts and cost estimates.
- `src/components/Modal.tsx`: native dialog, scroll lock and focus restoration.
- `tools/record-examples.mjs`: reproducible video recording.

No `.env` or API keys are needed. Vite's root is this directory and does not load the Python project's `.env`. Provider keys must remain on the server.
