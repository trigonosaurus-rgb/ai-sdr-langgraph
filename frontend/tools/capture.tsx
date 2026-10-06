// Development-only recording entry. Not linked or included in the production app.
import { useEffect, useReducer } from 'react'
import { createRoot } from 'react-dom/client'
import { RunPanel } from '../src/components/RunPanel'
import { emptyRun, reduceRun } from '../src/run'
import type { RunEvent } from '../src/run'
import { sampleBrief, draft, sources, sampleUsage } from './fixtures'
import '../src/styles.css'
import './capture.css'

const strategy =
  'Start with Northstar’s guided onboarding. Connect it to your ability to carry customer context from sales into onboarding. Ask whether manual steps exist: this is a hypothesis to explore, not a confirmed pain point.'
const id = 'recorded-fictional-example'
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
      })
      later(1700, {
        type: 'stage',
        stage: 'Strategy',
        message: 'Connecting guided onboarding to your offer.',
      })
      later(2100, { type: 'evidence', sources, strategy })
      later(3100, {
        type: 'stage',
        stage: 'Writing',
        message: 'Writing a short, grounded first message.',
      })
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
      })
      later(end + 1800, { type: 'completed', usage: sampleUsage })
    }
    if (new URLSearchParams(location.search).get('scene') === 'evidence') {
      dispatch(started)
      dispatch({ type: 'evidence', sources, strategy, runId: id, sequence: 1 })
      dispatch({
        type: 'draft_delta',
        field: 'subject',
        delta: draft.subject,
        runId: id,
        sequence: 2,
      })
      dispatch({
        type: 'draft_delta',
        field: 'body',
        delta: draft.body,
        runId: id,
        sequence: 3,
      })
      dispatch({
        type: 'completed',
        usage: sampleUsage,
        runId: id,
        sequence: 4,
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
        <span>OUTREACH / NORTHSTAR</span>
        <span>ILLUSTRATIVE RECORDING</span>
      </div>
      <RunPanel run={run} />
    </>
  )
}
document.documentElement.dataset.theme = 'dark'
createRoot(document.getElementById('root')!).render(<Capture />)
