import {
  CircleAlert,
  Check,
  FileText,
  LoaderCircle,
  Search,
  ShieldCheck,
  Square,
  Target,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { stageDurations, steps } from '../run'
import type { RunState } from '../run'

const icons = [Search, Target, FileText, ShieldCheck]
const seconds = (value: number | null | undefined) =>
  value == null
    ? '—'
    : `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 1, minimumFractionDigits: 1 }).format(value)} s`

// Ticks while a stage is active. The count starts from the local moment the stage event
// arrived and is anchored to the server's stage start, so it never invents finished timings.
function useStageClock(run: RunState) {
  const running = run.status === 'running'
  const [clock, setClock] = useState({ key: '', at: 0, now: 0 })
  const key = `${run.id}:${run.stage}`
  useEffect(() => {
    if (!running) return
    const at = performance.now()
    setClock({ key, at, now: at })
    const timer = window.setInterval(
      () => setClock((value) => ({ ...value, now: performance.now() })),
      100,
    )
    return () => window.clearInterval(timer)
  }, [running, key])
  if (!running || clock.key !== key) return null
  return (clock.now - clock.at) / 1000
}

export function RunTimeline({
  run,
  onCosts,
}: {
  run: RunState
  onCosts?: () => void
}) {
  const running = run.status === 'running',
    ready = run.status === 'ready',
    attention = run.status === 'needs_attention',
    failed = run.status === 'error',
    // Cancelled by the user: a deliberate stop, not an alarm.
    cancelled = failed && run.failureReason === 'cancelled'
  const stageIndex = run.stage ? steps.indexOf(run.stage) : -1
  const durations = stageDurations(run)
  const live = useStageClock(run)
  const currentStart = run.stage ? run.stageStartedMs[run.stage] : undefined
  const total = running
    ? live != null && currentStart != null
      ? currentStart / 1000 + live
      : null
    : (run.usage?.durationSeconds ??
      (run.endedMs != null ? run.endedMs / 1000 : null))
  return (
    <section className="run-rail" aria-labelledby="run-title">
      <header className="column-header">
        <h2 id="run-title">Run</h2>
        <span
          className={`status-badge ${ready ? 'success' : running ? 'working' : cancelled ? '' : failed || attention ? 'failed' : ''}`}
        >
          {ready
            ? 'Ready for review'
            : running
              ? 'In progress'
              : attention
                ? 'Needs attention'
                : failed
                  ? run.failureReason === 'error'
                    ? 'Failed'
                    : run.failureReason === 'cancelled'
                      ? 'Cancelled'
                      : 'Stopped'
                  : 'Not started'}
        </span>
      </header>
      <ol className="timeline" aria-label="Workflow progress">
        {steps.map((label, index) => {
          const done = ready || attention || index < stageIndex,
            current = running && index === stageIndex,
            broken = failed && index === stageIndex
          const Icon = icons[index]
          const state = broken
            ? cancelled
              ? 'stopped'
              : 'failed'
            : done
              ? 'complete'
              : current
                ? 'current'
                : 'pending'
          return (
            <li
              key={label}
              className={`timeline-step ${state}`}
              aria-current={current ? 'step' : undefined}
            >
              <span className="timeline-marker">
                {broken && cancelled ? (
                  <Square size={12} />
                ) : broken ? (
                  <CircleAlert size={15} />
                ) : done ? (
                  <Check size={15} strokeWidth={2.5} />
                ) : current ? (
                  <LoaderCircle size={15} className="spin" />
                ) : (
                  <Icon size={15} />
                )}
              </span>
              <span className="timeline-label">{label}</span>
              <span className="timeline-time">
                {done || broken
                  ? seconds(durations[label])
                  : current && live != null
                    ? seconds(live)
                    : ''}
              </span>
            </li>
          )
        })}
      </ol>
      {run.activity.length > 0 && (
        <div className="activity-feed">
          <span className="label-small">Activity</span>
          <p role="status" aria-live="polite">
            {run.activity.at(-1)}
          </p>
          {run.activity.length > 1 && (
            <details>
              <summary>Earlier activity</summary>
              <ol>
                {run.activity.slice(0, -1).map((message, index) => (
                  <li key={index}>{message}</li>
                ))}
              </ol>
            </details>
          )}
        </div>
      )}
      <div className="run-summary">
        <dl>
          <div>
            <dt>Total time</dt>
            <dd>{seconds(total)}</dd>
          </div>
          <div>
            <dt>Estimated cost</dt>
            <dd>
              {run.usage?.modelUsd != null && run.usage.searchUsd != null
                ? `$${(run.usage.modelUsd + run.usage.searchUsd).toFixed(4)}`
                : '—'}
            </dd>
          </div>
        </dl>
        {onCosts && (
          <button className="text-button" onClick={onCosts}>
            Usage details
          </button>
        )}
      </div>
    </section>
  )
}
