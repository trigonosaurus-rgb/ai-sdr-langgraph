import { useState } from 'react'
import type { KeyboardEvent } from 'react'
import {
  ArrowDownToLine,
  ArrowRight,
  Copy,
  Mail,
  Search,
  ShieldCheck,
  Target,
} from 'lucide-react'
import type { RunState } from '../run'
import type { Draft, ResultTab } from '../types'

const tabs = [
  { id: 'email', label: 'Email draft', icon: Mail },
  { id: 'research', label: 'Research', icon: Search },
  { id: 'strategy', label: 'Approach', icon: Target },
] as const

export function RunPanel({
  run,
  onExamples,
}: {
  run: RunState
  onExamples?: () => void
}) {
  const [tab, setTab] = useState<ResultTab>('email')
  const [edited, setEdited] = useState<{
    id: string | null
    draft: Draft
  } | null>(null)
  const [notice, setNotice] = useState('')
  const draft = edited?.id === run.id ? edited.draft : run.draft
  const running = run.status === 'running',
    ready = run.status === 'ready'
  function changeTab(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const next =
      event.key === 'ArrowRight'
        ? (index + 1) % tabs.length
        : event.key === 'ArrowLeft'
          ? (index + tabs.length - 1) % tabs.length
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? 2
              : -1
    if (next < 0) return
    event.preventDefault()
    setTab(tabs[next].id)
    document.getElementById(`tab-${tabs[next].id}`)?.focus()
  }
  function edit(field: keyof Draft, value: string) {
    setEdited({ id: run.id, draft: { ...draft, [field]: value } })
  }
  const text = () => `Subject: ${draft.subject}\n\n${draft.body}`
  async function copy() {
    try {
      await navigator.clipboard.writeText(text())
      setNotice('Email copied.')
    } catch {
      setNotice('Clipboard unavailable. Select the draft text to copy it.')
    }
  }
  function download() {
    const url = URL.createObjectURL(
      new Blob([text()], { type: 'text/plain;charset=utf-8' }),
    )
    const link = document.createElement('a')
    link.href = url
    link.download = 'outreach-draft.txt'
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return (
    <section className="draft-column" aria-labelledby="result-title">
      <div className="result-header">
        <span className="company-avatar">
          {run.company ? run.company.charAt(0) : <Mail size={16} />}
        </span>
        <div>
          <h2 id="result-title">{run.company || 'No company yet'}</h2>
          <p>{run.recipient ? `To ${run.recipient}` : 'Recipient not set'}</p>
        </div>
      </div>
      <div className="result-tabs" role="tablist" aria-label="Outreach results">
        {tabs.map(({ id, label, icon: Icon }, index) => (
          <button
            key={id}
            id={`tab-${id}`}
            role="tab"
            aria-selected={tab === id}
            aria-controls={`panel-${id}`}
            tabIndex={tab === id ? 0 : -1}
            className={tab === id ? 'selected' : ''}
            onClick={() => setTab(id)}
            onKeyDown={(event) => changeTab(event, index)}
          >
            <Icon size={15} />
            {label}
            {id === 'research' && run.sources.length > 0 && (
              <span className="tab-count">{run.sources.length}</span>
            )}
          </button>
        ))}
      </div>
      <div
        id={`panel-${tab}`}
        className="result-panel"
        role="tabpanel"
        aria-labelledby={`tab-${tab}`}
        tabIndex={0}
      >
        {run.error && (
          <div className="form-error" role="alert">
            {run.error} Any partial draft below is incomplete and has not passed
            review.
          </div>
        )}
        {tab === 'email' ? (
          draft.body || draft.subject ? (
            <>
              <div className="draft-meta">
                <span>
                  <span className="tiny-dot" />
                  {ready
                    ? edited
                      ? 'Edited by you'
                      : 'Ready for your review'
                    : run.status === 'error'
                      ? 'Incomplete draft'
                      : 'Writing as the response arrives'}
                </span>
                <span>
                  {draft.body.trim()
                    ? draft.body.trim().split(/\s+/).length
                    : 0}{' '}
                  words
                </span>
              </div>
              <div className="email-editor">
                <label htmlFor="subject">Subject</label>
                <input
                  id="subject"
                  value={draft.subject}
                  readOnly={!ready}
                  onChange={(e) => edit('subject', e.target.value)}
                />
                <div className="editor-rule" />
                <label className="sr-only" htmlFor="email-body">
                  Email body
                </label>
                {ready ? (
                  <textarea
                    id="email-body"
                    value={draft.body}
                    onChange={(e) => edit('body', e.target.value)}
                    rows={7}
                  />
                ) : (
                  <div className="streaming-draft" aria-label="Email body">
                    {draft.body}
                    {running && <span className="writing-caret" />}
                  </div>
                )}
              </div>
              {ready && (
                <div className="editor-actions">
                  <button className="primary-button" onClick={copy}>
                    <Copy size={15} />
                    Copy email
                  </button>
                  <button className="secondary-button" onClick={download}>
                    <ArrowDownToLine size={15} />
                    Download
                  </button>
                </div>
              )}
              {notice && (
                <p className="fine-print" role="status">
                  {notice}
                </p>
              )}
            </>
          ) : (
            <div className="empty-state">
              <h3>{running ? 'Researching the company' : 'No draft yet'}</h3>
              <p>
                {running
                  ? 'Progress is shown in the Run column. The draft appears here as it is written.'
                  : 'Fill in the brief and generate. The research, the approach and an editable draft will appear here.'}
              </p>
              {onExamples && !running && (
                <button className="text-button" onClick={onExamples}>
                  See an example run
                  <ArrowRight size={14} />
                </button>
              )}
            </div>
          )
        ) : tab === 'research' ? (
          <div className="research-content">
            {run.sources.length ? (
              run.sources.map((source) => (
                <details className="source-detail" key={source.id}>
                  <summary>
                    {source.title}
                    <span>{source.path}</span>
                  </summary>
                  <blockquote>{source.excerpt}</blockquote>
                </details>
              ))
            ) : (
              <div className="empty-state">
                <h3>No sources yet</h3>
                <p>
                  Company findings appear here after research, each with a link
                  to its source.
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="strategy-content">
            {run.strategy ? (
              <p className="empty-copy">{run.strategy}</p>
            ) : (
              <div className="empty-state">
                <h3>No approach yet</h3>
                <p>
                  The approach links a sourced company observation to your
                  offer. Unconfirmed needs are marked as hypotheses.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
      <footer className="result-footer">
        <ShieldCheck size={14} />
        Review every draft before sending it.
      </footer>
    </section>
  )
}
