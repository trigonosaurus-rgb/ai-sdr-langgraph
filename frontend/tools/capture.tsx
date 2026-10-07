// Development-only recording entry. Not linked or included in the production app.
import { useEffect, useReducer } from 'react'
import { createRoot } from 'react-dom/client'
import { RunPanel } from '../src/components/RunPanel'
import { RunTimeline } from '../src/components/RunTimeline'
import { emptyRun, reduceRun, steps } from '../src/run'
import type { RunEvent } from '../src/run'
import { sampleBrief, draft, sources, sampleUsage, strategy } from './fixtures'
import '../src/styles.css'
import './capture.css'

const id = 'recorded-fictional-example'
// Illustrative server timings in ms since the run started; the animation runs faster.
const timing = {
  Research: 0,
  Strategy: 4300,
  Writing: 6200,
  Review: 10600,
  end: 12400,
}
const started: RunEvent = {
  type: 'started',
  runId: id,
  sequence: 0,
  company: sampleBrief.company,
  recipient: sampleBrief.recipient,
}
function Capture() {
  const [run, dispatch] = useReducer(reduceRun, emptyRun)
  useEffect(() => {
    const timers: number[] = []
    function start() {
      let sequence = 1
      const later = (
        time: number,
        payload: Omit<RunEvent, 'runId' | 'sequence'> | Record<string, unknown>,
      ) => {
        const event = {
          ...payload,
          runId: id,
          sequence: sequence++,
        } as RunEvent
        timers.push(window.setTimeout(() => dispatch(event), time))
      }
      dispatch(started)
      later(100, {
        type: 'stage',
        stage: 'Research',
        message: 'Reading company product and onboarding pages.',
        elapsedMs: timing.Research,
      })
      later(1700, {
        type: 'stage',
        stage: 'Strategy',
        message: 'Connecting guided onboarding to your offer.',
        elapsedMs: timing.Strategy,
      })
      later(1650, { type: 'evidence', sources })
      later(2100, { type: 'strategy', strategy })
      later(3100, {
        type: 'stage',
        stage: 'Writing',
        message: 'Writing a short, grounded first message.',
        elapsedMs: timing.Writing,
      })
      later(3200, { type: 'draft_reset', attempt: 1 })
      later(3300, {
        type: 'draft_delta',
        field: 'subject',
        delta: draft.subject,
      })
      const chunks = draft.body.match(/.{1,8}/gs) ?? []
      chunks.forEach((delta, i) =>
        later(3550 + i * 120, { type: 'draft_delta', field: 'body', delta }),
      )
      const end = 3550 + chunks.length * 120
      later(end + 300, {
        type: 'stage',
        stage: 'Review',
        message: 'Checking claims, tone and the final question.',
        elapsedMs: timing.Review,
      })
      later(end + 1700, {
        type: 'review',
        attempt: 1,
        passed: true,
        issues: [],
      })
      later(end + 1800, {
        type: 'completed',
        outcome: 'ready',
        issues: [],
        usage: sampleUsage,
        elapsedMs: timing.end,
      })
    }
    if (new URLSearchParams(location.search).get('scene') === 'evidence') {
      dispatch(started)
      steps.forEach((stage, index) =>
        dispatch({
          type: 'stage',
          stage,
          message: 'Checking claims, tone and the final question.',
          elapsedMs: timing[stage],
          runId: id,
          sequence: 10 + index,
        }),
      )
      dispatch({ type: 'evidence', sources, runId: id, sequence: 19 })
      dispatch({ type: 'strategy', strategy, runId: id, sequence: 20 })
      dispatch({
        type: 'draft_delta',
        field: 'subject',
        delta: draft.subject,
        runId: id,
        sequence: 21,
      })
      dispatch({
        type: 'draft_delta',
        field: 'body',
        delta: draft.body,
        runId: id,
        sequence: 22,
      })
      dispatch({
        type: 'completed',
        outcome: 'ready',
        issues: [],
        usage: sampleUsage,
        elapsedMs: timing.end,
        runId: id,
        sequence: 23,
      })
    }
    window.addEventListener('recording:start', start, { once: true })
    document.body.dataset.captureReady = 'true'
    return () => {
      timers.forEach(clearTimeout)
      window.removeEventListener('recording:start', start)
    }
  }, [])
  return (
    <>
      <div className="capture-label">
        <span>Northstar</span>
        <span>Illustrative recording · fictional data</span>
      </div>
      <div className="capture-frame">
        <RunPanel run={run} />
        <RunTimeline run={run} />
      </div>
    </>
  )
}
document.documentElement.dataset.theme = 'dark'
createRoot(document.getElementById('root')!).render(<Capture />)
