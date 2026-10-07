import type { Brief, Draft, Review, Source, Strategy } from './types'

export const steps = ['Research', 'Strategy', 'Writing', 'Review'] as const
export type Stage = (typeof steps)[number]
export interface RunUsage {
  input: number | null
  cachedInput: number | null // subset of input
  output: number | null
  reasoning: number | null // subset of output, never added twice
  modelUsd: number | null
  searchUsd: number | null
  durationSeconds: number | null
  model: string
}
export type FailureReason =
  | 'insufficient_data'
  | 'website_mismatch'
  | 'cancelled'
  | 'daily_limit'
  | 'error'
export interface RunState {
  id: string | null
  sequence: number
  // needs_attention: a draft exists but did not pass review or the offer looks like a poor fit.
  status: 'idle' | 'running' | 'ready' | 'needs_attention' | 'error'
  stage: Stage | null
  company: string
  recipient: string
  activity: string[]
  draft: Draft
  attempt: number
  review: Review | null
  sources: Source[]
  strategy: Strategy | null
  issues: string[]
  error: string | null
  failureReason: FailureReason | null
  usage: RunUsage | null
  // Server-measured milliseconds since the run started: when each stage last began,
  // and the time spent in each stage across all its visits (rewrites revisit Writing and Review).
  stageStartedMs: Partial<Record<Stage, number>>
  stageSpentMs: Partial<Record<Stage, number>>
  endedMs: number | null
}
// elapsedMs is measured by the server from the run start, so stage timings survive reconnects.
// Mirrored by core/events.py; tests/test_events.py checks that the event types match.
type Payload =
  | { type: 'started'; company: string; recipient: string }
  | { type: 'stage'; stage: Stage; message: string; elapsedMs?: number }
  | { type: 'activity'; message: string }
  | { type: 'evidence'; sources: Source[] }
  | { type: 'strategy'; strategy: Strategy }
  | { type: 'draft_reset'; attempt: number }
  | { type: 'draft_delta'; field: keyof Draft; delta: string }
  | { type: 'review'; attempt: number; passed: boolean; issues: string[] }
  | {
      type: 'completed'
      outcome: 'ready' | 'needs_attention'
      issues: string[]
      usage: RunUsage | null
      elapsedMs?: number
    }
  | {
      type: 'failed'
      reason: FailureReason
      message: string
      stage: Stage | null
      elapsedMs?: number
    }
export type RunEvent = Payload & { runId: string; sequence: number }
export const emptyBrief: Brief = {
  company: '',
  website: '',
  recipient: '',
  offer: '',
  language: 'English',
  tone: 'Direct',
}
export const emptyRun: RunState = {
  id: null,
  sequence: -1,
  status: 'idle',
  stage: null,
  company: '',
  recipient: '',
  activity: [],
  draft: { subject: '', body: '' },
  attempt: 0,
  review: null,
  sources: [],
  strategy: null,
  issues: [],
  error: null,
  failureReason: null,
  usage: null,
  stageStartedMs: {},
  stageSpentMs: {},
  endedMs: null,
}

// Seconds spent in each stage; null for the stage still running, unvisited stages, or unknown timing.
export function stageDurations(run: RunState): Record<Stage, number | null> {
  const result = {} as Record<Stage, number | null>
  for (const stage of steps) {
    const spent = run.stageSpentMs[stage]
    const open = run.status === 'running' && run.stage === stage
    result[stage] = spent != null && !open ? spent / 1000 : null
  }
  return result
}

// Adds the time since the current stage began to its total.
function closeStage(
  state: RunState,
  elapsedMs: number | undefined,
): Partial<Record<Stage, number>> {
  const start = state.stage ? state.stageStartedMs[state.stage] : undefined
  if (!state.stage || start == null || elapsedMs == null || elapsedMs < start)
    return state.stageSpentMs
  return {
    ...state.stageSpentMs,
    [state.stage]: (state.stageSpentMs[state.stage] ?? 0) + (elapsedMs - start),
  }
}

// View-state contract for the future streaming adapter; no simulated timers in the app.
// Sequence numbers make replayed events harmless. Only started can begin another run.
export function reduceRun(state: RunState, event: RunEvent): RunState {
  if (event.type === 'started') {
    if (state.id === event.runId) return state
    return {
      ...emptyRun,
      id: event.runId,
      sequence: event.sequence,
      status: 'running',
      company: event.company,
      recipient: event.recipient,
    }
  }
  if (
    event.runId !== state.id ||
    event.sequence <= state.sequence ||
    state.status !== 'running'
  )
    return state
  const next = { ...state, sequence: event.sequence }
  switch (event.type) {
    case 'stage':
      return {
        ...next,
        stage: event.stage,
        activity: [...state.activity, event.message],
        stageSpentMs: closeStage(state, event.elapsedMs),
        stageStartedMs:
          event.elapsedMs == null
            ? state.stageStartedMs
            : { ...state.stageStartedMs, [event.stage]: event.elapsedMs },
      }
    case 'activity':
      return { ...next, activity: [...state.activity, event.message] }
    case 'evidence':
      return { ...next, sources: event.sources }
    case 'strategy':
      return { ...next, strategy: event.strategy }
    case 'draft_reset':
      // A rewrite replaces the previous draft; its review no longer applies.
      return {
        ...next,
        attempt: event.attempt,
        draft: { subject: '', body: '' },
        review: null,
      }
    case 'draft_delta':
      return {
        ...next,
        draft: {
          ...state.draft,
          [event.field]: state.draft[event.field] + event.delta,
        },
      }
    case 'review':
      return {
        ...next,
        review: {
          attempt: event.attempt,
          passed: event.passed,
          issues: event.issues,
        },
      }
    case 'completed':
      return {
        ...next,
        status: event.outcome,
        issues: event.issues,
        usage: event.usage,
        stageSpentMs: closeStage(state, event.elapsedMs),
        endedMs: event.elapsedMs ?? null,
      }
    case 'failed':
      return {
        ...next,
        status: 'error',
        error: event.message,
        failureReason: event.reason,
        stageSpentMs: closeStage(state, event.elapsedMs),
        endedMs: event.elapsedMs ?? null,
      }
  }
}
