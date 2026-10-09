import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { RunPanel } from './RunPanel'
import { emptyRun } from '../run'
import type { RunState } from '../run'
import type { Source } from '../types'

const source = (id: number, url: string, extra: Partial<Source> = {}) => ({
  id,
  claim: `Claim ${id}`,
  title: `Page ${id}`,
  url,
  path: url.replace(/^\w+:\/*/, ''),
  excerpt: `“Quote ${id}”`,
  ...extra,
})

async function openResearch(sources: Source[]) {
  const run: RunState = { ...emptyRun, id: 'run-1', status: 'ready', sources }
  render(<RunPanel run={run} />)
  await userEvent.click(screen.getByRole('tab', { name: /Research/ }))
  return screen.getByRole('list', { name: 'Facts' })
}

describe('research facts', () => {
  it('shows each fact with its quote and a link to the source', async () => {
    const list = await openResearch([
      source(1, 'https://acme.com/about'),
      source(2, 'https://news.example/acme'),
    ])
    const facts = within(list).getAllByRole('listitem')
    expect(facts).toHaveLength(2)
    expect(within(facts[0]).getByText('Claim 1')).toBeVisible()
    // Quote marks are dropped: the blockquote already marks a quote.
    expect(within(facts[0]).getByText('Quote 1')).toBeVisible()
    const link = within(facts[0]).getByRole('link', { name: /Page 1/ })
    expect(link).toHaveAttribute('href', 'https://acme.com/about')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('never turns a non-http source into a link', async () => {
    const list = await openResearch([
      source(1, 'javascript:alert(1)'),
      source(2, 'not a url'),
    ])
    expect(within(list).queryByRole('link')).toBeNull()
    expect(within(list).getByText('Page 1')).toBeVisible()
  })

  it('keeps quote marks inside an excerpt', async () => {
    const list = await openResearch([
      source(1, 'https://acme.com', { excerpt: 'Called “Flow” internally' }),
    ])
    expect(within(list).getByText('Called “Flow” internally')).toBeVisible()
  })
})

describe('email body', () => {
  afterEach(() => vi.restoreAllMocks())

  it('grows with the text instead of scrolling inside the field', async () => {
    // jsdom has no layout: test the measured fallback for browsers without field-sizing.
    vi.spyOn(CSS, 'supports').mockReturnValue(false)
    let contentHeight = 520
    vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockImplementation(
      () => contentHeight,
    )
    const run: RunState = {
      ...emptyRun,
      id: 'run-1',
      status: 'ready',
      draft: { subject: 'Hello', body: 'A long draft' },
    }
    render(<RunPanel run={run} />)
    const body = screen.getByLabelText('Email body')
    expect(body).toHaveStyle({ height: '520px' })
    contentHeight = 610
    await userEvent.type(body, ' that keeps going')
    expect(body).toHaveStyle({ height: '610px' })
  })
})

describe('approach', () => {
  const strategy = {
    observation: 'Acme is hiring 30 engineers for a new analytics team.',
    factIds: [2, 9],
    offerLink: 'Contract engineers can start while hiring continues.',
    hypotheses: ['The team may need help before the hires land.'],
    angle: 'Bridge the hiring gap.',
    offerFit: 'weak' as const,
    fitReason: 'Hiring is planned, so contractors may not be needed.',
  }
  async function openApproach() {
    const run: RunState = {
      ...emptyRun,
      id: 'run-1',
      status: 'needs_attention',
      sources: [
        source(1, 'https://acme.com'),
        source(2, 'https://acme.com/jobs'),
      ],
      strategy,
    }
    render(<RunPanel run={run} />)
    await userEvent.click(screen.getByRole('tab', { name: /Approach/ }))
  }

  it('shows the fit, its reason and each part of the approach', async () => {
    await openApproach()
    expect(screen.getByText('Weak fit')).toBeVisible()
    expect(screen.getByText(strategy.fitReason)).toBeVisible()
    for (const heading of [
      'Observation',
      'How your offer connects',
      'Angle of the email',
      'To confirm, not to claim',
    ])
      expect(screen.getByRole('heading', { name: heading })).toBeVisible()
    // Guesses are listed under their heading, not prefixed one by one.
    expect(screen.getByText(strategy.hypotheses[0])).toBeVisible()
    expect(screen.queryByText(/Hypothesis, not confirmed/)).toBeNull()
  })

  it('links the observation to the facts it rests on', async () => {
    await openApproach()
    // Fact 9 was not kept by research, so it is not offered as a link.
    expect(screen.queryByRole('button', { name: /fact 9/ })).toBeNull()
    await userEvent.click(
      screen.getByRole('button', { name: 'Show fact 2 in Research' }),
    )
    expect(screen.getByRole('tab', { name: /Research/ })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    const fact = document.getElementById('fact-2')
    expect(fact).toHaveClass('focused')
    expect(fact).toHaveFocus()
    await userEvent.click(screen.getByRole('tab', { name: /Email draft/ }))
    await userEvent.click(screen.getByRole('tab', { name: /Research/ }))
    expect(document.getElementById('fact-2')).not.toHaveClass('focused')
  })
})
