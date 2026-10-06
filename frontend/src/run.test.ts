import { describe, expect, it } from 'vitest'
import { emptyRun, reduceRun, stageDurations } from './run'
import type { RunEvent } from './run'
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
      runId: 'r1',
      sequence: 2,
      message: 'Disconnected',
    })
    state = reduceRun(state, {
      type: 'completed',
      runId: 'r1',
      sequence: 3,
      usage: null,
    })
    expect(state.status).toBe('error')
    expect(state.draft.body).toBe('Hello')
  })
  it('starts a new run cleanly and does not reset a run on a replayed start', () => {
    const state = reduceRun(reduceRun(emptyRun, started), delta)
    expect(reduceRun(state, started)).toBe(state)
    expect(reduceRun(state, { ...started, runId: 'r2' }).draft.body).toBe('')
  })
  it('derives stage durations from server timings and leaves the active stage open', () => {
    let state = reduceRun(emptyRun, started)
    const stage = (
      sequence: number,
      name: 'Research' | 'Strategy',
      elapsedMs: number,
    ): RunEvent => ({
      type: 'stage',
      stage: name,
      message: name,
      elapsedMs,
      runId: 'r1',
      sequence,
    })
    state = reduceRun(state, stage(1, 'Research', 0))
    state = reduceRun(state, stage(2, 'Strategy', 3100))
    expect(stageDurations(state)).toMatchObject({
      Research: 3.1,
      Strategy: null,
    })
    state = reduceRun(state, {
      type: 'completed',
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
})
