// Development-only recording entry. Not linked or included in the production app.
// Replays a real run exported with tools/export-run.mjs: the same events the browser received,
// in order and with their timing, except that long waits for the model are shortened.
//   /tools/capture.html?run=<name>&scene=workflow|evidence
import { useEffect, useReducer } from 'react'
import { createRoot } from 'react-dom/client'
import { RunPanel } from '../src/components/RunPanel'
import { RunTimeline } from '../src/components/RunTimeline'
import { emptyRun, reduceRun } from '../src/run'
import type { RunEvent } from '../src/run'
import type { Brief } from '../src/types'
import '../src/styles.css'
import './capture.css'

interface Fixture {
  runId: string
  recordedAt: string
  brief: Brief
  events: { atMs: number; event: RunEvent }[]
}

// Stage times and the total shown on screen are the server's; only the playback is shortened.
const MAX_WAIT_MS = 1200

const fixtures = import.meta.glob<Fixture>('./runs/*.json', {
  eager: true,
  import: 'default',
})
const params = new URLSearchParams(location.search)
const fixture = fixtures[`./runs/${params.get('run')}.json`]
const scene = params.get('scene') === 'evidence' ? 'evidence' : 'workflow'

function Capture({ fixture }: { fixture: Fixture }) {
  const [run, dispatch] = useReducer(reduceRun, emptyRun)
  useEffect(() => {
    const timers: number[] = []
    function play() {
      let at = 0
      fixture.events.forEach(({ atMs, event }, index) => {
        const gap = index ? atMs - fixture.events[index - 1].atMs : 0
        at += Math.min(gap, MAX_WAIT_MS)
        timers.push(window.setTimeout(() => dispatch(event), at))
      })
      timers.push(
        window.setTimeout(() => (document.body.dataset.played = 'true'), at),
      )
    }
    if (scene === 'evidence') {
      fixture.events.forEach(({ event }) => dispatch(event))
      document.body.dataset.played = 'true'
    } else {
      window.addEventListener('recording:start', play, { once: true })
    }
    document.body.dataset.captureReady = 'true'
    return () => {
      timers.forEach(clearTimeout)
      window.removeEventListener('recording:start', play)
    }
  }, [fixture])
  const day = new Date(fixture.recordedAt).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
  return (
    <>
      <div className="capture-label">
        <span>
          {fixture.brief.company} · {fixture.brief.website}
        </span>
        <span>
          {scene === 'workflow'
            ? `Real run, ${day} · waits shortened`
            : `Real run, ${day}`}
        </span>
      </div>
      <div className="capture-frame">
        <RunPanel
          run={run}
          initialTab={scene === 'evidence' ? 'research' : 'email'}
        />
        <RunTimeline run={run} />
      </div>
    </>
  )
}

document.documentElement.dataset.theme = 'dark'
createRoot(document.getElementById('root')!).render(
  fixture ? (
    <Capture fixture={fixture} />
  ) : (
    <p>
      No recording fixture “{params.get('run')}”. Export one with
      tools/export-run.mjs.
    </p>
  ),
)
