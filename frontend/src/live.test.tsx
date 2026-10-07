import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import App from './App'
import { parseEvent, validateBrief } from './api'
import { emptyBrief } from './run'
import type { RunEvent } from './run'
import { FakeEventSource, mockApi, online, serviceStatus } from './test/server'

const brief = {
  company: 'Acme',
  website: 'acme.com',
  recipient: 'VP of Engineering',
  offer: 'Contract data engineers',
  language: 'English' as const,
  tone: 'Direct' as const,
}

let sequence = 0
function event(runId: string, payload: Record<string, unknown>): RunEvent {
  return { ...payload, runId, sequence: sequence++ } as RunEvent
}
const started = (runId: string) =>
  event(runId, {
    type: 'started',
    company: 'Acme',
    recipient: 'VP of Engineering',
  })

async function fillBrief(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Company name'), brief.company)
  await user.type(screen.getByLabelText('Company website'), brief.website)
  await user.type(screen.getByLabelText('Recipient role'), brief.recipient)
  await user.type(screen.getByLabelText('Your offer'), brief.offer)
}

async function generate(user: ReturnType<typeof userEvent.setup>) {
  const button = screen.getByRole('button', { name: 'Generate outreach' })
  await waitFor(() => expect(button).toBeEnabled()) // after the health check
  await user.click(button)
}

beforeEach(() => {
  sequence = 0
  history.replaceState(null, '', '/')
})

describe('brief validation', () => {
  it('mirrors the server rules', () => {
    expect(validateBrief(brief)).toEqual({})
    expect(Object.keys(validateBrief(emptyBrief)).sort()).toEqual([
      'company',
      'offer',
      'recipient',
      'website',
    ])
    expect(validateBrief({ ...brief, website: 'acme' }).website).toMatch(
      /domain/,
    )
    expect(
      validateBrief({ ...brief, website: 'https://www.acme.com/a' }),
    ).toEqual({})
    expect(validateBrief({ ...brief, company: '   ' }).company).toBeTruthy()
  })

  it('shows field errors on Generate instead of sending an invalid brief', async () => {
    const user = userEvent.setup()
    const fetch = mockApi(online)
    render(<App />)
    await user.type(screen.getByLabelText('Company name'), 'Acme')
    await generate(user)
    expect(screen.getByText('Enter the company website.')).toBeInTheDocument()
    expect(screen.getByLabelText('Company website')).toHaveFocus()
    expect(screen.getByLabelText('Company website')).toHaveAttribute(
      'aria-invalid',
      'true',
    )
    await user.type(screen.getByLabelText('Company website'), 'acme.com')
    expect(
      screen.queryByText('Enter the company website.'),
    ).not.toBeInTheDocument()
    expect(fetch.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(
      false,
    )
  })
})

describe('event validation', () => {
  it('accepts contract events and rejects malformed ones', () => {
    const good = {
      type: 'draft_delta',
      field: 'body',
      delta: 'Hi',
      runId: 'r',
      sequence: 3,
    }
    expect(parseEvent(good)).toEqual(good)
    expect(parseEvent({ ...good, field: 'footer' })).toBeNull()
    expect(parseEvent({ ...good, sequence: '3' })).toBeNull()
    expect(parseEvent({ ...good, type: 'telemetry' })).toBeNull()
    expect(
      parseEvent({
        type: 'failed',
        reason: 'cancelled',
        message: 'Stopped.',
        stage: null,
        elapsedMs: 10,
        runId: 'r',
        sequence: 9,
      }),
    ).not.toBeNull()
  })
})

describe('live run', () => {
  it('starts a run, streams the draft and ends only on the reviewed completion', async () => {
    const user = userEvent.setup()
    const fetch = mockApi({
      ...online,
      'POST /api/runs': { status: 201, body: { runId: 'r1' } },
    })
    render(<App />)
    await fillBrief(user)
    await generate(user)

    const [, init] = fetch.mock.calls.find(([url]) => url === '/api/runs')!
    expect(JSON.parse(init!.body as string)).toEqual(brief)
    const stream = FakeEventSource.latest()
    expect(stream.url).toBe('/api/runs/r1/events?after=-1')
    expect(localStorage.getItem('ai-sdr.active-run.v1')).toBe('r1')

    act(() => {
      stream.open()
      stream.send(
        started('r1'),
        event('r1', {
          type: 'stage',
          stage: 'Writing',
          message: 'Writing the first draft',
          elapsedMs: 10,
        }),
        event('r1', { type: 'draft_reset', attempt: 1 }),
        event('r1', { type: 'draft_delta', field: 'subject', delta: 'Hello' }),
        event('r1', { type: 'draft_delta', field: 'body', delta: 'First ' }),
        event('r1', { type: 'draft_delta', field: 'body', delta: 'line.' }),
        // A foreign run and a malformed event never reach the view.
        event('other', {
          type: 'draft_delta',
          field: 'body',
          delta: ' INJECTED',
        }),
        { type: 'draft_delta', field: 'body', delta: ' BROKEN', runId: 'r1' },
      )
    })
    expect(screen.getByLabelText('Email body')).toHaveTextContent('First line.')
    expect(screen.getByLabelText('Email body')).not.toHaveTextContent(
      /INJECTED|BROKEN/,
    )
    expect(screen.getByRole('button', { name: 'Cancel run' })).toBeEnabled()
    expect(screen.getByLabelText('Company name')).toBeDisabled()

    act(() => {
      stream.send(
        event('r1', {
          type: 'completed',
          outcome: 'ready',
          issues: [],
          usage: null,
          elapsedMs: 900,
        }),
      )
    })
    expect(stream.readyState).toBe(FakeEventSource.CLOSED)
    expect(screen.getByText('Ready for review')).toBeInTheDocument()
    expect(screen.getByLabelText('Subject')).toHaveValue('Hello')
    expect(screen.getByLabelText('Company name')).toBeEnabled()
  })

  it('restores the run and its brief after a reload', async () => {
    localStorage.setItem('ai-sdr.active-run.v1', 'r7')
    mockApi({
      ...online,
      'GET /api/runs/r7': {
        body: {
          runId: 'r7',
          status: 'running',
          reason: null,
          brief,
          createdAt: '2026-10-07T12:00:00.000+00:00',
          finishedAt: null,
          lastSequence: 4,
        },
      },
    })
    render(<App />)
    await waitFor(() =>
      expect(screen.getByLabelText('Company name')).toHaveValue('Acme'),
    )
    const stream = FakeEventSource.latest()
    expect(stream.url).toBe('/api/runs/r7/events?after=-1') // replay from the start
    act(() => {
      stream.open()
      stream.send(
        started('r7'),
        event('r7', { type: 'draft_delta', field: 'body', delta: 'Kept.' }),
      )
    })
    expect(screen.getByLabelText('Email body')).toHaveTextContent('Kept.')
  })

  it('forgets a saved run the server no longer has', async () => {
    localStorage.setItem('ai-sdr.active-run.v1', 'gone')
    mockApi({
      ...online,
      'GET /api/runs/gone': { status: 404, body: { detail: 'Run not found' } },
    })
    render(<App />)
    await waitFor(() =>
      expect(localStorage.getItem('ai-sdr.active-run.v1')).toBeNull(),
    )
    expect(FakeEventSource.instances).toEqual([])
  })

  it('cancels through the server and shows the acknowledgement from the stream', async () => {
    const user = userEvent.setup()
    const fetch = mockApi({
      ...online,
      'POST /api/runs': { status: 201, body: { runId: 'r2' } },
      'POST /api/runs/r2/cancel': { status: 202, body: { runId: 'r2' } },
    })
    render(<App />)
    await fillBrief(user)
    await generate(user)
    const stream = FakeEventSource.latest()
    act(() => stream.send(started('r2')))

    await user.click(screen.getByRole('button', { name: 'Cancel run' }))
    expect(
      fetch.mock.calls.some(([url]) => url === '/api/runs/r2/cancel'),
    ).toBe(true)
    expect(screen.getByRole('button', { name: 'Cancelling…' })).toBeDisabled()

    act(() =>
      stream.send(
        event('r2', {
          type: 'failed',
          reason: 'cancelled',
          message: 'The run was cancelled. Nothing was finished.',
          stage: 'Research',
          elapsedMs: 300,
        }),
      ),
    )
    const rail = screen.getByRole('region', { name: 'Run' })
    expect(within(rail).getByText('Cancelled')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Generate outreach' }),
    ).toBeEnabled()
  })

  it('explains a refused start', async () => {
    const user = userEvent.setup()
    mockApi({
      ...online,
      'POST /api/runs': {
        status: 429,
        body: {
          detail: 'A run from your address is already in progress.',
        },
      },
    })
    render(<App />)
    await fillBrief(user)
    await generate(user)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'A run from your address is already in progress.',
    )
    expect(FakeEventSource.instances).toEqual([])
    expect(
      screen.getByRole('button', { name: 'Generate outreach' }),
    ).toBeEnabled()
  })

  it('says how many runs the visitor has left', async () => {
    mockApi({
      'GET /api/status': {
        body: serviceStatus({ runsToday: 1, runsThisMonth: 4 }),
      },
    })
    render(<App />)
    expect(
      await screen.findByText(
        'Each run makes real model and search calls. Runs left: 2 today, 6 this month.',
      ),
    ).toBeInTheDocument()
  })

  it('turns Generate off when a refused start shows the quota is used up', async () => {
    const user = userEvent.setup()
    let refused = false
    const nextRunAt = new Date(Date.now() + 3 * 3600_000).toISOString()
    mockApi({
      'GET /api/status': () => ({
        body: refused
          ? serviceStatus({ runsToday: 3, runsThisMonth: 3, nextRunAt })
          : serviceStatus(),
      }),
      'POST /api/runs': () => {
        refused = true
        return {
          status: 429,
          body: {
            detail:
              'You have used your 3 runs for today. The next one is available in 3 h.',
          },
        }
      },
    })
    render(<App />)
    await fillBrief(user)
    await generate(user)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'You have used your 3 runs for today.',
    )
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Generate outreach' }),
      ).toBeDisabled(),
    )
  })

  it('shows a large notice when the developer paused the service', async () => {
    mockApi({
      'GET /api/status': {
        body: serviceStatus({}, '2026-11-01T00:00:00+00:00'),
      },
    })
    render(<App />)
    expect(
      await screen.findByRole('heading', {
        name: 'Service paused by the developer',
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/live generation is off until November 1/),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Generate outreach' }),
    ).toBeDisabled()
    expect(
      screen.getByRole('button', { name: /View examples/ }),
    ).toBeInTheDocument()
  })

  it('pauses the service when the budget runs out during a run', async () => {
    const user = userEvent.setup()
    let ended = false
    mockApi({
      'GET /api/status': () => ({
        body: ended
          ? serviceStatus({ runsToday: 1 }, '2026-11-01T00:00:00+00:00')
          : serviceStatus(),
      }),
      'POST /api/runs': { status: 201, body: { runId: 'r9' } },
    })
    render(<App />)
    await fillBrief(user)
    await generate(user)
    const stream = FakeEventSource.latest()
    ended = true
    act(() =>
      stream.send(
        started('r9'),
        event('r9', {
          type: 'failed',
          reason: 'budget_exhausted',
          message:
            "The service was paused by the developer: this month's demo budget ran out during the run. Nothing was finished.",
          stage: 'Writing',
          elapsedMs: 900,
        }),
      ),
    )
    const rail = screen.getByRole('region', { name: 'Run' })
    expect(within(rail).getByText('Stopped')).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', {
        name: 'Service paused by the developer',
      }),
    ).toBeInTheDocument()
  })
})
