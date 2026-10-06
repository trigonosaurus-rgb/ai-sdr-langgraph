import { ArrowRight, Globe2 } from 'lucide-react'
import type { Brief } from '../types'

export function BriefForm({
  brief,
  onChange,
}: {
  brief: Brief
  onChange: (brief: Brief) => void
}) {
  function update<K extends keyof Brief>(key: K, value: Brief[K]) {
    onChange({ ...brief, [key]: value })
  }
  return (
    <section className="brief-column" aria-labelledby="brief-title">
      <header className="column-header">
        <h2 id="brief-title">Brief</h2>
      </header>
      <form onSubmit={(event) => event.preventDefault()}>
        <fieldset>
          <legend className="sr-only">Outreach brief</legend>
          <div className="field">
            <label htmlFor="company">Company name</label>
            <input
              id="company"
              value={brief.company}
              onChange={(e) => update('company', e.target.value)}
              placeholder="Acme Inc."
              maxLength={100}
              autoComplete="organization"
            />
          </div>
          <div className="field">
            <label htmlFor="website">Company website</label>
            <div className="input-wrap">
              <Globe2 size={16} />
              <input
                id="website"
                type="url"
                value={brief.website}
                onChange={(e) => update('website', e.target.value)}
                placeholder="https://company.com"
                maxLength={500}
              />
            </div>
          </div>
          <div className="field">
            <label htmlFor="recipient">Recipient role</label>
            <input
              id="recipient"
              value={brief.recipient}
              onChange={(e) => update('recipient', e.target.value)}
              placeholder="Head of Customer Success"
              maxLength={150}
            />
          </div>
          <div className="field">
            <label htmlFor="offer">Your offer</label>
            <textarea
              id="offer"
              className="offer-input"
              value={brief.offer}
              onChange={(e) => update('offer', e.target.value)}
              placeholder="What you offer, who it helps and the problem it solves."
              maxLength={1500}
              rows={4}
              aria-describedby="offer-hint"
            />
            <p className="field-hint" id="offer-hint">
              Concrete, checkable claims make a stronger email.
            </p>
          </div>
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
        <button
          className="primary-button run-button"
          disabled
          aria-describedby="service-status"
        >
          Generate outreach
          <ArrowRight size={16} />
        </button>
        <p className="run-disclaimer" id="service-status">
          <span className="connection-dot" />
          Live generation is not connected yet.
        </p>
      </form>
    </section>
  )
}
