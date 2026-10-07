import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { RunPanel } from './components/RunPanel'
import { emptyRun } from './run'

beforeEach(() => {
  history.replaceState(null, '', '/')
})
const posts = () =>
  vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === 'POST')
describe('workspace', () => {
  it('starts with an empty brief, no sample result and no fabricated usage', async () => {
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
    // The test has no backend, so the service reads as unavailable and nothing can start.
    expect(
      await screen.findByText(
        'The service is unavailable, so generation is off.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Generate outreach' }),
    ).toBeDisabled()
    expect(posts()).toEqual([])
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
  it('lets the user edit and clear the brief without launching a run', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByLabelText('Company name'), 'Real company')
    fireEvent.submit(screen.getByLabelText('Company name').closest('form')!)
    expect(screen.queryByLabelText('Email body')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /New outreach/ }))
    expect(screen.getByLabelText('Company name')).toHaveValue('')
    expect(posts()).toEqual([])
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
