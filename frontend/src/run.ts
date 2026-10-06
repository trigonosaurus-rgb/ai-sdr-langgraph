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
}
type Payload =
  | { type: 'started'; company: string; recipient: string }
  | { type: 'stage'; stage: Stage; message: string }
  | { type: 'draft_delta'; field: keyof Draft; delta: string }
  | { type: 'evidence'; sources: Source[]; strategy: string }
  | { type: 'completed'; usage: RunUsage | null }
  | { type: 'failed'; message: string }
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
      return { ...next, status: 'ready', usage: event.usage }
    case 'failed':
      return { ...next, status: 'error', error: event.message }
  }
}
