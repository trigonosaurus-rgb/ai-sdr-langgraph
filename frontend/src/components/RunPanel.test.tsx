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
