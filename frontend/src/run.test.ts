import { describe, expect, it } from 'vitest'
import { emptyRun, reduceRun, stageDurations } from './run'
import type { RunEvent, RunState, Stage } from './run'
const started: RunEvent = {
  type: 'started',
  runId: 'r1',
  sequence: 0,
  company: 'Company',
  recipient: 'Founder',
}
const delta: RunEvent = {
  type: 'draft_delta',
  field: 'body',
  delta: 'Hello',
  runId: 'r1',
  sequence: 1,
}
type Payload = RunEvent extends infer E
  ? E extends RunEvent
    ? Omit<E, 'runId' | 'sequence'>
    : never
  : never
// Applies payloads to a started run with consecutive sequence numbers.
function play(...payloads: Payload[]): RunState {
  return payloads.reduce<RunState>(
    (state, payload, index) =>
      reduceRun(state, {
        ...payload,
        runId: 'r1',
        sequence: index + 1,
      } as RunEvent),
    reduceRun(emptyRun, started),
  )
}
const stage = (name: Stage, elapsedMs: number): Payload => ({
  type: 'stage',
  stage: name,
  message: name,
  elapsedMs,
})
describe('stream view state', () => {
  it('appends deltas once and ignores events from other runs', () => {
    let state = reduceRun(reduceRun(emptyRun, started), delta)
    state = reduceRun(state, delta)
    state = reduceRun(state, { ...delta, runId: 'other', sequence: 2 })
    expect(state.draft.body).toBe('Hello')
    state = reduceRun(state, { ...delta, sequence: 2, delta: ' world' })
    expect(state.draft.body).toBe('Hello world')
  })
  it('preserves partial output on failure and refuses a late success', () => {
    let state = reduceRun(reduceRun(emptyRun, started), delta)
    state = reduceRun(state, {
      type: 'failed',
      reason: 'error',
      message: 'Disconnected',
      stage: 'Writing',
      runId: 'r1',
      sequence: 2,
    })
    state = reduceRun(state, {
      type: 'completed',
      outcome: 'ready',
      issues: [],
      usage: null,
      runId: 'r1',
      sequence: 3,
    })
    expect(state.status).toBe('error')
    expect(state.failureReason).toBe('error')
    expect(state.draft.body).toBe('Hello')
  })
  it('starts a new run cleanly and does not reset a run on a replayed start', () => {
    const state = reduceRun(reduceRun(emptyRun, started), delta)
    expect(reduceRun(state, started)).toBe(state)
    expect(reduceRun(state, { ...started, runId: 'r2' }).draft.body).toBe('')
  })
  it('replaces the draft and clears its review on a rewrite', () => {
    const state = play(
      { type: 'draft_reset', attempt: 1 },
      { type: 'draft_delta', field: 'body', delta: 'First' },
      { type: 'review', attempt: 1, passed: false, issues: ['Too long'] },
    )
    expect(state.review).toEqual({
      attempt: 1,
      passed: false,
      issues: ['Too long'],
    })
    const rewritten = reduceRun(state, {
      type: 'draft_reset',
      attempt: 2,
      runId: 'r1',
      sequence: 4,
    })
    expect(rewritten.attempt).toBe(2)
    expect(rewritten.draft).toEqual({ subject: '', body: '' })
    expect(rewritten.review).toBeNull()
  })
  it('ends with needs_attention, keeping the draft and the issues', () => {
    const state = play(
      { type: 'draft_delta', field: 'body', delta: 'Draft' },
      {
        type: 'completed',
        outcome: 'needs_attention',
        issues: ['Claims a fact that is not in the sources.'],
        usage: null,
      },
    )
    expect(state.status).toBe('needs_attention')
    expect(state.issues).toEqual(['Claims a fact that is not in the sources.'])
    expect(state.draft.body).toBe('Draft')
  })
  it('keeps evidence and strategy from separate events', () => {
    const state = play(
      {
        type: 'evidence',
        sources: [
          {
            id: 1,
            claim: 'Claim',
            title: 'Title',
            url: 'https://a.example/x',
            path: 'a.example/x',
            excerpt: 'Quote',
          },
        ],
      },
      {
        type: 'strategy',
        strategy: {
          observation: 'Observation',
          factIds: [1],
          offerLink: 'Link',
          hypotheses: ['Maybe'],
          angle: 'Angle',
          offerFit: 'good',
          fitReason: 'Reason',
        },
      },
    )
    expect(state.sources).toHaveLength(1)
    expect(state.strategy?.factIds).toEqual([1])
  })
  it('derives stage durations from server timings and leaves the active stage open', () => {
    let state = play(stage('Research', 0), stage('Strategy', 3100))
    expect(stageDurations(state)).toMatchObject({
      Research: 3.1,
      Strategy: null,
    })
    state = reduceRun(state, {
      type: 'completed',
      outcome: 'ready',
      issues: [],
      usage: null,
      elapsedMs: 4500,
      runId: 'r1',
      sequence: 3,
    })
    expect(stageDurations(state)).toMatchObject({
      Research: 3.1,
      Strategy: 1.4,
      Writing: null,
      Review: null,
    })
  })
  it('adds up time across rewrites and ignores activity for timing', () => {
    const state = play(
      stage('Research', 0),
      { type: 'activity', message: 'Found 6 pages' },
      stage('Strategy', 2000),
      stage('Writing', 3000),
      stage('Review', 5000),
      stage('Writing', 6000),
      stage('Review', 9000),
      {
        type: 'completed',
        outcome: 'ready',
        issues: [],
        usage: null,
        elapsedMs: 9500,
      },
    )
    expect(state.activity).toContain('Found 6 pages')
    expect(stageDurations(state)).toEqual({
      Research: 2,
      Strategy: 1,
      Writing: 5,
      Review: 1.5,
    })
  })
})
