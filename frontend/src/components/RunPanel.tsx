import { useState } from 'react'
import type { KeyboardEvent } from 'react'
import {
  ArrowDownToLine,
  ArrowRight,
  Check,
  Copy,
  FileText,
  LoaderCircle,
  Mail,
  Search,
  ShieldCheck,
  Target,
  Timer,
} from 'lucide-react'
import { steps } from '../run'
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
  const stageIndex = run.stage ? steps.indexOf(run.stage) : -1
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
    <div className="result-column">
      <section className="workflow-card" aria-labelledby="workflow-title">
        <div className="section-heading">
          <h2 id="workflow-title">Run status</h2>
          <span
            className={`status-badge ${ready ? 'success' : running ? 'working' : ''}`}
          >
            {running && <LoaderCircle size={13} className="spin" />}
            {ready
              ? 'Ready for review'
              : running
                ? `${run.stage ?? 'Starting'}…`
                : run.status === 'error'
                  ? 'Needs attention'
                  : 'Not started'}
          </span>
        </div>
        <ol className="workflow-steps" aria-label="Workflow progress">
          {steps.map((label, index) => {
            const done = ready || index < stageIndex,
              current = running && index === stageIndex
            const Icon = [Search, Target, FileText, ShieldCheck][index]
            return (
              <li
                key={label}
                className={`${done ? 'complete' : ''} ${current ? 'current' : ''}`}
                aria-current={current ? 'step' : undefined}
              >
                <span className="step-icon">
                  {done ? (
                    <Check size={17} />
                  ) : current ? (
                    <LoaderCircle size={17} className="spin" />
                  ) : (
                    <Icon size={17} />
                  )}
                </span>
                {label}
              </li>
            )
          })}
        </ol>
        {run.activity.length > 0 && (
          <div className="activity-feed">
            <span className="label-small">ACTIVITY</span>
            <p role="status" aria-live="polite">
              {run.activity.at(-1)}
            </p>
            <details>
              <summary>Earlier activity</summary>
              <ol>
                {run.activity.slice(0, -1).map((message, index) => (
                  <li key={index}>{message}</li>
                ))}
              </ol>
            </details>
          </div>
        )}
      </section>
      <section className="result-card" aria-labelledby="result-title">
        <div className="result-header">
          <span className="company-avatar">
            {run.company ? run.company.charAt(0) : <Mail size={18} />}
          </span>
          <div>
            <h2 id="result-title">{run.company || 'Your next conversation'}</h2>
            <p>
              {run.recipient
                ? `To ${run.recipient}`
                : 'From a useful observation to a thoughtful email.'}
            </p>
          </div>
          <span
            className="response-duration"
            aria-label="Run duration"
            title="Total request duration"
          >
            <Timer size={17} />
            {run.usage?.durationSeconds == null
              ? '—'
              : new Intl.NumberFormat('en-US', {
                  maximumFractionDigits: 1,
                }).format(run.usage.durationSeconds)}{' '}
            s
          </span>
        </div>
        <div
          className="result-tabs"
          role="tablist"
          aria-label="Outreach results"
        >
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
              <Icon size={16} />
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
              {run.error} Any partial draft below is incomplete and has not
              passed review.
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
                <span className="empty-illustration">
                  <FileText size={32} strokeWidth={1} />
                </span>
                <span className="label-small">ROOM FOR SOMETHING RELEVANT</span>
                <h3>
                  {running
                    ? 'Finding the right starting point.'
                    : 'Good outreach starts with context.'}
                </h3>
                <p>
                  {running
                    ? 'Research and the current activity appear here. The draft will arrive as it is written.'
                    : 'Add a company and your offer. This space will hold the research, the approach and a draft you can make your own.'}
                </p>
                {onExamples && (
                  <button className="text-button" onClick={onExamples}>
                    See the workflow in action
                    <ArrowRight size={15} />
                  </button>
                )}
              </div>
            )
          ) : tab === 'research' ? (
            <div className="research-content">
              <span className="label-small">SOURCE MATERIAL</span>
              <h3>Evidence before assumptions.</h3>
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
                <p className="empty-copy">
                  Company findings and their sources will appear here after
                  research. No sources have been collected yet.
                </p>
              )}
            </div>
          ) : (
            <div className="strategy-content">
              <span className="label-small">THE CONVERSATION ANGLE</span>
              <h3>A reason to reach out.</h3>
              <p className="empty-copy">
                {run.strategy ||
                  'The approach will connect a supported company observation to your offer, keeping unconfirmed needs clearly marked as hypotheses.'}
              </p>
            </div>
          )}
        </div>
      </section>
      <footer className="result-footer">
        <span>
          <ShieldCheck size={14} />
          Review required before sending
        </span>
        <span>You have the final say.</span>
      </footer>
    </div>
  )
}
