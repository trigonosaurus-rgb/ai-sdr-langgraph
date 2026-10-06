import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import App from './App'
import { Metrics } from './components/Metrics'
import { RunPanel } from './components/RunPanel'
import { emptyRun } from './run'

beforeEach(() => {
  history.replaceState(null, '', '/')
})
describe('workspace', () => {
  it('starts with an empty brief, no sample result and no fabricated usage', () => {
    localStorage.setItem(
      'ai-sdr.sample-draft.v1',
      JSON.stringify({
        body: 'Old sample',
        subject: 'Old sample',
        language: 'English',
        tone: 'Direct',
      }),
    )
    render(<App />)
    expect(screen.getByLabelText('Company name')).toHaveValue('')
    expect(screen.queryByText('Northstar')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Email body')).not.toBeInTheDocument()
    expect(screen.queryByText('Total tokens')).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Generate outreach' }),
    ).toBeDisabled()
    expect(fetch).not.toHaveBeenCalled()
  })
  it('moves costs into a dismissible dialog and treats missing usage as unknown', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'Run costs' }))
    const dialog = screen.getByRole('dialog', { name: 'Run costs' })
    expect(within(dialog).getByText('Total tokens')).toBeInTheDocument()
    expect(dialog).toHaveTextContent('No run yet')
    expect(dialog).not.toHaveTextContent('$0.0000')
    await user.click(
      within(dialog).getByRole('button', { name: 'Close dialog' }),
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
  it('lets the user edit and clear the brief without launching a fake run', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByLabelText('Company name'), 'Real company')
    fireEvent.submit(screen.getByLabelText('Company name').closest('form')!)
    expect(screen.queryByLabelText('Email body')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /New outreach/ }))
    expect(screen.getByLabelText('Company name')).toHaveValue('')
    expect(fetch).not.toHaveBeenCalled()
  })
  it('keeps unknown search cost from producing a falsely complete total', () => {
    render(
      <Metrics
        usage={{
          input: 100,
          cachedInput: 20,
          output: 50,
          reasoning: 15,
          modelUsd: 0.001,
          searchUsd: null,
          durationSeconds: 3,
          model: 'configured-model',
        }}
      />,
    )
    expect(screen.getByText('150')).toBeInTheDocument()
    expect(screen.getByText('$0.0010')).toBeInTheDocument()
    expect(screen.getByText('Estimated cost').parentElement).toHaveTextContent(
      '—',
    )
  })
  it('allows edits and copying only after review completes', async () => {
    const user = userEvent.setup()
    const run = {
      ...emptyRun,
      id: 'r1',
      status: 'running' as const,
      draft: { subject: 'Hello', body: 'Partial response' },
    }
    const view = render(<RunPanel run={run} />)
    expect(screen.getByLabelText('Email body')).toHaveTextContent(
      'Partial response',
    )
    expect(
      screen.queryByRole('button', { name: 'Copy email' }),
    ).not.toBeInTheDocument()
    view.rerender(<RunPanel run={{ ...run, status: 'ready' }} />)
    await user.clear(screen.getByLabelText('Subject'))
    await user.type(screen.getByLabelText('Subject'), 'Edited subject')
    await user.click(screen.getByRole('button', { name: 'Copy email' }))
    expect(await navigator.clipboard.readText()).toBe(
      'Subject: Edited subject\n\nPartial response',
    )
  })
})
