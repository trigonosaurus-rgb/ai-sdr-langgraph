import { ArrowRight, Globe2, LoaderCircle, Square } from 'lucide-react'
import type { ReactNode } from 'react'
import { briefLimits } from '../api'
import type { BriefErrors } from '../api'
import type { Brief } from '../types'

export type FormStatus = {
  tone: 'online' | 'offline' | 'working' | 'error'
  text: string
}

function Field({
  id,
  label,
  error,
  hint,
  children,
}: {
  id: keyof Brief
  label: string
  error?: string
  hint?: string
  children: ReactNode
}) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {error ? (
        <p className="field-error" id={`${id}-error`}>
          {error}
        </p>
      ) : (
        hint && (
          <p className="field-hint" id={`${id}-hint`}>
            {hint}
          </p>
        )
      )}
    </div>
  )
}

export function BriefForm({
  brief,
  onChange,
  errors,
  locked,
  running,
  starting,
  cancelling,
  canGenerate,
  status,
  onGenerate,
  onCancel,
}: {
  brief: Brief
  onChange: (brief: Brief) => void
  errors: BriefErrors
  locked: boolean // a run of this brief is in progress
  running: boolean
  starting: boolean
  cancelling: boolean
  canGenerate: boolean
  status: FormStatus
  onGenerate: () => void
  onCancel: () => void
}) {
  function update<K extends keyof Brief>(key: K, value: Brief[K]) {
    onChange({ ...brief, [key]: value })
  }
  const described = (id: keyof Brief, hint = false) =>
    errors[id] ? `${id}-error` : hint ? `${id}-hint` : undefined
  const text = (id: 'company' | 'recipient') => ({
    id,
    value: brief[id],
    onChange: (e: { target: { value: string } }) => update(id, e.target.value),
    maxLength: briefLimits[id],
    'aria-invalid': errors[id] ? true : undefined,
    'aria-describedby': described(id),
  })
  return (
    <section className="brief-column" aria-labelledby="brief-title">
      <header className="column-header">
        <h2 id="brief-title">Brief</h2>
      </header>
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault()
          if (!running && !starting) onGenerate()
        }}
      >
        <fieldset disabled={locked}>
          <legend className="sr-only">Outreach brief</legend>
          <Field id="company" label="Company name" error={errors.company}>
            <input
              {...text('company')}
              placeholder="Acme Inc."
              autoComplete="organization"
            />
          </Field>
          <Field id="website" label="Company website" error={errors.website}>
            <div className="input-wrap">
              <Globe2 size={16} />
              <input
                id="website"
                inputMode="url"
                value={brief.website}
                onChange={(e) => update('website', e.target.value)}
                placeholder="company.com"
                maxLength={briefLimits.website}
                aria-invalid={errors.website ? true : undefined}
                aria-describedby={described('website')}
              />
            </div>
          </Field>
          <Field id="recipient" label="Recipient role" error={errors.recipient}>
            <input
              {...text('recipient')}
              placeholder="Head of Customer Success"
            />
          </Field>
          <Field
            id="offer"
            label="Your offer"
            error={errors.offer}
            hint="Concrete, checkable claims make a stronger email."
          >
            <textarea
              id="offer"
              className="offer-input"
              value={brief.offer}
              onChange={(e) => update('offer', e.target.value)}
              placeholder="What you offer, who it helps and the problem it solves."
              maxLength={briefLimits.offer}
              rows={4}
              aria-invalid={errors.offer ? true : undefined}
              aria-describedby={described('offer', true)}
            />
          </Field>
          <div className="field-row">
            <div className="field">
              <label htmlFor="language">Language</label>
              <select
                id="language"
                value={brief.language}
                onChange={(e) =>
                  update('language', e.target.value as Brief['language'])
                }
              >
                <option>English</option>
                <option>Russian</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="tone">Tone</label>
              <select
                id="tone"
                value={brief.tone}
                onChange={(e) =>
                  update('tone', e.target.value as Brief['tone'])
                }
              >
                <option>Direct</option>
                <option>Warm</option>
              </select>
            </div>
          </div>
        </fieldset>
        {running ? (
          <button
            type="button"
            className="secondary-button run-button"
            onClick={onCancel}
            disabled={cancelling}
            aria-describedby="service-status"
          >
            {cancelling ? (
              <LoaderCircle size={15} className="spin" />
            ) : (
              <Square size={13} />
            )}
            {cancelling ? 'Cancelling…' : 'Cancel run'}
          </button>
        ) : (
          <button
            type="submit"
            className="primary-button run-button"
            disabled={!canGenerate || starting}
            aria-describedby="service-status"
          >
            {starting ? 'Starting…' : 'Generate outreach'}
            {starting ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <ArrowRight size={16} />
            )}
          </button>
        )}
        <p
          className={`run-disclaimer ${status.tone}`}
          id="service-status"
          role={status.tone === 'error' ? 'alert' : 'status'}
        >
          <span className="connection-dot" />
          {status.text}
        </p>
      </form>
    </section>
  )
}
