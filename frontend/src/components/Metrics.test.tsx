import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { Metrics } from './Metrics'
import type { LlmCallCost, RunCost, UsageTotals } from '../api'
import { mockApi } from '../test/server'

const totals: UsageTotals = {
  runs: 1,
  llmCalls: 5,
  searchCalls: 3,
  input: 7000,
  cachedInput: 1000,
  output: 2500,
  reasoning: 1200,
  searchCredits: 3,
  modelUsd: 0.0151,
  searchUsd: 0.024,
  durationSeconds: 21.5,
  models: ['gpt-5.4-mini-2026-03-17'],
  priceVersions: ['2026-10-07'],
  incomplete: false,
}
const call = (stage: string, attempt = 1, extra = {}): LlmCallCost => ({
  stage,
  attempt,
  model: 'gpt-5.4-mini-2026-03-17',
  input: 1000,
  cachedInput: 0,
  output: 500,
  reasoning: 200,
  costUsd: 0.003,
  durationMs: 1000,
  failed: false,
  ...extra,
})
const search = {
  topic: 'general',
  results: 5,
  credits: 1,
  costUsd: 0.008,
  durationMs: 500,
  failed: false,
}
const runCost: RunCost = {
  runId: 'r1',
  status: 'ready',
  totals,
  llmCalls: [
    call('Research'),
    call('Strategy'),
    call('Writing'),
    call('Review'),
    call('Writing', 2),
  ],
  searchCalls: [search, search, search],
}
const budget = {
  usd: 1,
  spentUsd: 0.1234,
  searchCredits: 25,
  spentSearchCredits: 9,
  resetsAt: '2026-10-08T00:00:00+00:00',
}

describe('run costs', () => {
  it('shows a run with its total, every step and rewrite, and search apart', async () => {
    mockApi({ 'GET /api/runs/r1/usage': { body: runCost } })
    render(<Metrics runId="r1" runStatus="ready" />)
    expect(await screen.findByText('Usage for this run.', { exact: false }))
    expect(screen.getByText('Estimated cost').parentElement).toHaveTextContent(
      '$0.0391',
    )
    expect(screen.getByText('9,500')).toBeInTheDocument() // input + output, cached and reasoning not added
    const table = screen.getByRole('table', { name: 'By step' })
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows.map((row) => row.querySelector('th')?.textContent)).toEqual([
      'Web search, 3 requests',
      'Research',
      'Strategy',
      'Writing',
      'Review',
      'Writing, draft 2',
    ])
    expect(rows[0]).toHaveTextContent('3 credits$0.0240')
    expect(screen.getByText(/Prices as of 2026-10-07/)).toBeInTheDocument()
    expect(screen.queryByText(/Incomplete data/)).not.toBeInTheDocument()
  })

  it('marks unknown cost as unknown and the totals as incomplete', async () => {
    mockApi({
      'GET /api/runs/r1/usage': {
        body: {
          ...runCost,
          totals: { ...totals, modelUsd: null, incomplete: true },
          llmCalls: [
            call('Research', 1, {
              input: null,
              output: null,
              costUsd: null,
              failed: true,
            }),
          ],
        },
      },
    })
    render(<Metrics runId="r1" runStatus="error" />)
    expect(await screen.findByText(/Incomplete data/)).toBeInTheDocument()
    expect(screen.getByText('Estimated cost').parentElement).toHaveTextContent(
      '—',
    )
    expect(screen.getByText('Model cost').nextSibling).toHaveTextContent('—')
    expect(screen.getByText(/Search cost/).nextSibling).toHaveTextContent(
      '$0.0240',
    )
    expect(
      screen.getByRole('row', { name: /Research \(failed\)/ }),
    ).toHaveTextContent('— / —')
    expect(screen.queryByText('$0.0000')).not.toBeInTheDocument()
  })

  it('shows the visitor’s runs over a period and the service budget', async () => {
    const user = userEvent.setup()
    const fetch = mockApi({
      'GET /api/usage?period=24h': {
        body: {
          period: '24h',
          since: '2026-10-06T12:00:00+00:00',
          totals: { ...totals, runs: 2 },
          budget,
        },
      },
    })
    render(<Metrics runId={null} />)
    expect(screen.getByText(/No run yet/)).toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: '24 hours' }))
    expect(
      await screen.findByText(
        /2 runs from your address over the last 24 hours/,
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'Service budget today: $0.12 of $1.00 and 9 of 25 search credits',
        { exact: false },
      ),
    ).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('refreshes a run in progress as it moves to the next stage', async () => {
    const fetch = mockApi({
      'GET /api/runs/r1/usage': {
        body: { ...runCost, status: 'running', llmCalls: [] },
      },
    })
    const view = render(
      <Metrics runId="r1" runStatus="running" runStage="Research" />,
    )
    expect(
      await screen.findByText(/This run is in progress/),
    ).toBeInTheDocument()
    view.rerender(
      <Metrics runId="r1" runStatus="running" runStage="Strategy" />,
    )
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('says so when usage cannot be loaded, without inventing numbers', async () => {
    render(<Metrics runId="r1" runStatus="ready" />)
    expect(
      await screen.findByText(
        'The service is unavailable. Try again in a minute.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('Estimated cost').parentElement).toHaveTextContent(
      '—',
    )
  })
})
