import type { Brief, Draft, Source } from './types'

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
export interface RunState {
  id: string | null
  sequence: number
  status: 'idle' | 'running' | 'ready' | 'error'
  stage: Stage | null
  company: string
  recipient: string
  activity: string[]
  draft: Draft
  sources: Source[]
  strategy: string
  error: string | null
  usage: RunUsage | null
  // Server-measured milliseconds since the run started.
  stageStartedMs: Partial<Record<Stage, number>>
  endedMs: number | null
}
// elapsedMs is measured by the server from the run start, so stage timings survive reconnects.
type Payload =
  | { type: 'started'; company: string; recipient: string }
  | { type: 'stage'; stage: Stage; message: string; elapsedMs?: number }
  | { type: 'draft_delta'; field: keyof Draft; delta: string }
  | { type: 'evidence'; sources: Source[]; strategy: string }
  | { type: 'completed'; usage: RunUsage | null; elapsedMs?: number }
  | { type: 'failed'; message: string; elapsedMs?: number }
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
  sources: [],
  strategy: '',
  error: null,
  usage: null,
  stageStartedMs: {},
  endedMs: null,
}

// Duration of each finished stage in seconds; null while running or when timing is unknown.
export function stageDurations(run: RunState): Record<Stage, number | null> {
  const result = {} as Record<Stage, number | null>
  steps.forEach((stage, index) => {
    const start = run.stageStartedMs[stage]
    const nextStart = steps
      .slice(index + 1)
      .map((next) => run.stageStartedMs[next])
      .find((value) => value != null)
    const end = nextStart ?? run.endedMs
    result[stage] =
      start != null && end != null && end >= start ? (end - start) / 1000 : null
  })
  return result
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
        stageStartedMs:
          event.elapsedMs == null
            ? state.stageStartedMs
            : { ...state.stageStartedMs, [event.stage]: event.elapsedMs },
      }
    case 'draft_delta':
      return {
        ...next,
        draft: {
          ...state.draft,
          [event.field]: state.draft[event.field] + event.delta,
        },
      }
    case 'evidence':
      return { ...next, sources: event.sources, strategy: event.strategy }
    case 'completed':
      return {
        ...next,
        status: 'ready',
        usage: event.usage,
        endedMs: event.elapsedMs ?? null,
      }
    case 'failed':
      return {
        ...next,
        status: 'error',
        error: event.message,
        endedMs: event.elapsedMs ?? null,
      }
  }
}
