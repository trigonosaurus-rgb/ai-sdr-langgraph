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
    <section className="brief-card" aria-labelledby="brief-title">
      <div className="card-heading">
        <h2 id="brief-title">Your brief</h2>
        <span className="label-small">01</span>
      </div>
      <form onSubmit={(event) => event.preventDefault()}>
        <fieldset>
          <legend className="sr-only">Outreach brief</legend>
          <div className="field-group-label">
            <span>PROSPECT</span>
            <span className="small-line" />
          </div>
          <label htmlFor="company">Company name</label>
          <input
            id="company"
            value={brief.company}
            onChange={(e) => update('company', e.target.value)}
            placeholder="Who would you like to reach?"
            maxLength={100}
            autoComplete="organization"
          />
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
          <label htmlFor="recipient">Recipient role</label>
          <input
            id="recipient"
            value={brief.recipient}
            onChange={(e) => update('recipient', e.target.value)}
            placeholder="e.g. Head of Customer Success"
            maxLength={150}
          />
          <div className="field-group-label offer-label">
            <span>YOUR OFFER</span>
            <span className="small-line" />
          </div>
          <label htmlFor="offer">How can you help?</label>
          <textarea
            id="offer"
            className="offer-input"
            value={brief.offer}
            onChange={(e) => update('offer', e.target.value)}
            placeholder="What you offer, who it helps, and the problem it solves."
            maxLength={1500}
            rows={4}
            aria-describedby="offer-hint"
          />
          <p className="field-hint" id="offer-hint">
            Specific, verifiable value makes a stronger message.
          </p>
          <div className="field-row">
            <div>
              <label htmlFor="language">Email language</label>
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
            <div>
              <label htmlFor="tone">Tone of voice</label>
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
          <ArrowRight size={17} />
        </button>
        <p className="run-disclaimer" id="service-status">
          <span className="connection-dot" />
          Live generation is not connected yet.
        </p>
      </form>
    </section>
  )
}
