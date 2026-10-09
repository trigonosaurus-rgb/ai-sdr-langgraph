import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import {
  ArrowDownToLine,
  ArrowRight,
  CircleHelp,
  Copy,
  ExternalLink,
  Mail,
  Search,
  ShieldCheck,
  Target,
} from 'lucide-react'
import type { RunState } from '../run'
import type { Draft, ResultTab, Strategy } from '../types'

// Source URLs come from web search: only http(s) becomes a link, never javascript: or data:.
function safeHref(url: string): string | null {
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'https:' || parsed.protocol === 'http:'
      ? parsed.href
      : null
  } catch {
    return null
  }
}

// Excerpts are verbatim quotes, often wrapped in quote marks; the blockquote already shows that.
const unquote = (text: string) =>
  text
    .trim()
    .replace(/^["“«„]([^]*)["”»“]$/, '$1')
    .trim()

// The body grows with its text rather than scrolling inside a fixed box, so the draft keeps its
// height when streaming ends and the editable field replaces it. Browsers with
// `field-sizing: content` do this in CSS; elsewhere the height is measured on each change.
const sizesInCss = () =>
  typeof CSS !== 'undefined' && CSS.supports?.('field-sizing', 'content')

function fitHeight(field: HTMLTextAreaElement) {
  // Collapsing to measure can scroll the column; restore where the reader was.
  const column = field.closest('.draft-column')
  const top = column?.scrollTop ?? 0,
    y = window.scrollY
  field.style.height = 'auto'
  field.style.height = `${field.scrollHeight}px`
  if (column) column.scrollTop = top
  if (window.scrollY !== y) window.scrollTo(window.scrollX, y)
}

function BodyField({
  value,
  onChange,
}: {
  value: string
  onChange: (value: string) => void
}) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useLayoutEffect(() => {
    if (!sizesInCss() && ref.current) fitHeight(ref.current)
  }, [value])
  useEffect(() => {
    // Wrapping changes with the width: refit when the column is resized.
    const field = ref.current
    if (sizesInCss() || !field || typeof ResizeObserver === 'undefined') return
    let width = field.clientWidth
    const observer = new ResizeObserver(() => {
      if (field.clientWidth === width) return
      width = field.clientWidth
      fitHeight(field)
    })
    observer.observe(field)
    return () => observer.disconnect()
  }, [])
  return (
    <textarea
      ref={ref}
      id="email-body"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}

const FIT: Record<Strategy['offerFit'], string> = {
  good: 'Strong fit',
  weak: 'Weak fit',
  poor: 'Poor fit',
}

// The approach as the strategist built it: how well the offer fits, the observation and the facts
// it rests on, how the offer connects, the email's angle, and the guesses left for the recipient.
function Approach({
  strategy,
  factIds,
  onFact,
}: {
  strategy: Strategy
  factIds: number[] // the observation's facts that research kept
  onFact: (id: number) => void
}) {
  return (
    <div className="approach">
      <div className={`fit fit-${strategy.offerFit}`}>
        <span className="fit-badge">
          <span className="fit-dot" aria-hidden="true" />
          {FIT[strategy.offerFit]}
        </span>
        {strategy.fitReason && <p>{strategy.fitReason}</p>}
      </div>
      <section className="approach-part" aria-labelledby="approach-observation">
        <div className="approach-heading">
          <h3 id="approach-observation">Observation</h3>
          {factIds.length > 0 && (
            <span className="fact-refs">
              based on facts
              {factIds.map((id) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => onFact(id)}
                  aria-label={`Show fact ${id} in Research`}
                >
                  {id}
                </button>
              ))}
            </span>
          )}
        </div>
        <p>{strategy.observation}</p>
      </section>
      <section className="approach-part" aria-labelledby="approach-offer">
        <h3 id="approach-offer">How your offer connects</h3>
        <p>{strategy.offerLink}</p>
      </section>
      {strategy.angle && (
        <section className="approach-part" aria-labelledby="approach-angle">
          <h3 id="approach-angle">Angle of the email</h3>
          <p>{strategy.angle}</p>
        </section>
      )}
      {strategy.hypotheses.length > 0 && (
        <section className="approach-part" aria-labelledby="approach-guesses">
          <h3 id="approach-guesses">To confirm, not to claim</h3>
          <ul className="hypotheses">
            {strategy.hypotheses.map((hypothesis) => (
              <li key={hypothesis}>
                <CircleHelp size={15} aria-hidden="true" />
                <span>{hypothesis}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

const tabs = [
  { id: 'email', label: 'Email draft', icon: Mail },
  { id: 'research', label: 'Research', icon: Search },
  { id: 'strategy', label: 'Approach', icon: Target },
] as const

export function RunPanel({
  run,
  paused = false,
  onExamples,
  initialTab = 'email',
}: {
  run: RunState
  paused?: boolean // live generation is stopped for visitors
  onExamples?: () => void
  initialTab?: ResultTab
}) {
  const [tab, setTab] = useState<ResultTab>(initialTab)
  const [edited, setEdited] = useState<{
    id: string | null
    draft: Draft
  } | null>(null)
  const [notice, setNotice] = useState('')
  // A fact opened from the approach: Research scrolls to it and marks it.
  const [focusedFact, setFocusedFact] = useState<number | null>(null)
  useEffect(() => {
    if (tab !== 'research' || focusedFact == null) return
    const item = document.getElementById(`fact-${focusedFact}`)
    const reduced = window.matchMedia?.(
      '(prefers-reduced-motion: reduce)',
    ).matches
    item?.scrollIntoView?.({
      block: 'center',
      behavior: reduced ? 'auto' : 'smooth',
    })
    item?.focus({ preventScroll: true })
  }, [tab, focusedFact])
  function showFact(id: number) {
    setFocusedFact(id)
    setTab('research')
  }
  function selectTab(next: ResultTab) {
    setFocusedFact(null)
    setTab(next)
  }
  const draft = edited?.id === run.id ? edited.draft : run.draft
  const running = run.status === 'running',
    attention = run.status === 'needs_attention',
    finished = run.status === 'ready' || attention
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
    selectTab(tabs[next].id)
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
          <p>{run.recipient ? `To: ${run.recipient}` : 'Recipient not set'}</p>
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
            onClick={() => selectTab(id)}
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
          <div
            className={
              run.failureReason === 'cancelled' ? 'form-note' : 'form-error'
            }
            role="alert"
          >
            {run.error}
            {(draft.subject || draft.body) &&
              ' The partial draft below is incomplete and has not passed review.'}
          </div>
        )}
        {attention && run.issues.length > 0 && (
          <div className="form-error" role="status">
            Check before sending: {run.issues.join(' ')}
          </div>
        )}
        {tab === 'email' ? (
          draft.body || draft.subject ? (
            <>
              <div className="draft-meta">
                <span>
                  <span className="tiny-dot" />
                  {finished
                    ? edited
                      ? 'Edited by you'
                      : attention
                        ? 'Needs your attention'
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
                  readOnly={!finished}
                  onChange={(e) => edit('subject', e.target.value)}
                />
                <div className="editor-rule" />
                <label className="sr-only" htmlFor="email-body">
                  Email body
                </label>
                {finished ? (
                  <BodyField
                    value={draft.body}
                    onChange={(value) => edit('body', value)}
                  />
                ) : (
                  <div className="streaming-draft" aria-label="Email body">
                    {draft.body}
                    {running && <span className="writing-caret" />}
                  </div>
                )}
              </div>
              {finished && (
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
            <div className="draft-empty">
              <div className="empty-state">
                <h3>{running ? 'Researching the company' : 'No draft yet'}</h3>
                <p>
                  {running
                    ? 'Progress is shown in the Run column. The draft appears here as it is written.'
                    : paused
                      ? 'Live generation is off for now. A run produces three things:'
                      : 'Fill in the brief and generate. Each run produces three things:'}
                </p>
              </div>
              {running ? (
                // Shown only while something is actually loading.
                <div className="draft-skeleton loading" aria-hidden="true">
                  <span className="skeleton-subject" />
                  <span className="skeleton-rule" />
                  <span style={{ width: '92%' }} />
                  <span style={{ width: '84%' }} />
                  <span style={{ width: '60%' }} />
                </div>
              ) : (
                <ol className="outcome-list" aria-label="What a run produces">
                  <li>
                    <Search size={16} />
                    <span>
                      <strong>Sourced facts</strong>
                      What the company does, each point linked to the page it
                      came from.
                    </span>
                  </li>
                  <li>
                    <Target size={16} />
                    <span>
                      <strong>An approach</strong>
                      Why your offer fits them. Unconfirmed needs are marked as
                      guesses.
                    </span>
                  </li>
                  <li>
                    <Mail size={16} />
                    <span>
                      <strong>A short email</strong>
                      Editable, ready to copy. Nothing is sent for you.
                    </span>
                  </li>
                </ol>
              )}
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
              <ol className="fact-list" aria-label="Facts">
                {run.sources.map((source) => {
                  const href = safeHref(source.url)
                  return (
                    <li
                      className={
                        focusedFact === source.id ? 'fact focused' : 'fact'
                      }
                      key={source.id}
                      id={`fact-${source.id}`}
                      tabIndex={-1}
                    >
                      <p className="fact-claim">
                        <span className="fact-number">{source.id}</span>
                        {source.claim}
                      </p>
                      <blockquote>{unquote(source.excerpt)}</blockquote>
                      {href ? (
                        <a
                          className="fact-source"
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <span>{source.title}</span>
                          <span className="fact-path">
                            {source.path}
                            <ExternalLink size={12} aria-hidden="true" />
                          </span>
                        </a>
                      ) : (
                        <span className="fact-source">
                          <span>{source.title}</span>
                          <span className="fact-path">{source.path}</span>
                        </span>
                      )}
                    </li>
                  )
                })}
              </ol>
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
              <Approach
                strategy={run.strategy}
                factIds={run.strategy.factIds.filter((id) =>
                  run.sources.some((source) => source.id === id),
                )}
                onFact={showFact}
              />
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
