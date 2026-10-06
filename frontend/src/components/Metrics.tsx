import { Coins, Layers3, Timer } from 'lucide-react'
import { useState } from 'react'
import { CostPeriodControl } from './CostPeriodControl'
import type { CostPeriod } from './CostPeriodControl'
import type { RunUsage } from '../run'
const number = (value: number | null | undefined) =>
  value == null ? '—' : value.toLocaleString('en-US')
const money = (value: number | null | undefined) =>
  value == null ? '—' : `$${value.toFixed(4)}`

export function Metrics({
  usage: runUsage,
  history,
}: {
  usage: RunUsage | null
  history?: Partial<Record<'30d' | '24h', RunUsage>>
}) {
  const [period, setPeriod] = useState<CostPeriod>('run')
  const usage = period === 'run' ? runUsage : (history?.[period] ?? null)
  const total =
    usage?.modelUsd != null && usage.searchUsd != null
      ? usage.modelUsd + usage.searchUsd
      : null
  const tokens =
    usage?.input != null && usage.output != null
      ? usage.input + usage.output
      : null
  return (
    <section className="usage-section" aria-label="Usage details">
      <CostPeriodControl value={period} onChange={setPeriod} />
      <p className="costs-intro">
        {usage
          ? `${period === 'run' ? 'Usage for this run' : period === '24h' ? 'Usage over the last 24 hours' : 'Usage over the last 30 days'}. Amounts are estimates in USD.`
          : period === 'run'
            ? 'No run yet. Actual usage will appear here after your first generation.'
            : `Usage history for the last ${period === '24h' ? '24 hours' : '30 days'} is not connected yet.`}
      </p>
      <div className="metrics-grid">
        <div className="metric">
          <span className="metric-label">
            <Coins size={15} />
            Estimated cost
          </span>
          <strong>
            {money(total)}
            <span> USD</span>
          </strong>
          <span className="muted">Model + search</span>
        </div>
        <div className="metric">
          <span className="metric-label">
            <Layers3 size={15} />
            Total tokens
          </span>
          <strong>{number(tokens)}</strong>
          <span className="muted">Input + output</span>
        </div>
        <div className="metric">
          <span className="metric-label">
            <Timer size={15} />
            {period === 'run' ? 'Duration' : 'Total runtime'}
          </span>
          <strong>
            {number(usage?.durationSeconds)}
            <span> sec</span>
          </strong>
          <span className="muted">
            {period === 'run' ? 'Entire run' : 'All runs in this period'}
          </span>
        </div>
      </div>
      <dl className="cost-breakdown">
        <div>
          <dt>Input tokens</dt>
          <dd>{number(usage?.input)}</dd>
        </div>
        <div className="subset">
          <dt>Of which cached</dt>
          <dd>{number(usage?.cachedInput)}</dd>
        </div>
        <div>
          <dt>Output tokens</dt>
          <dd>{number(usage?.output)}</dd>
        </div>
        <div className="subset">
          <dt>Of which reasoning</dt>
          <dd>{number(usage?.reasoning)}</dd>
        </div>
        <div>
          <dt>Model cost</dt>
          <dd>{money(usage?.modelUsd)}</dd>
        </div>
        <div>
          <dt>Search cost</dt>
          <dd>{money(usage?.searchUsd)}</dd>
        </div>
      </dl>
      <p className="fine-print">
        {usage ? `Model: ${usage.model}. ` : ''}Cached input and reasoning are
        included in their respective totals, never counted twice. A dash means
        the value is unavailable.
      </p>
      <div className="costs-bottom">
        <span>Estimated usage, not an invoice.</span>
        <span>Daily totals will appear when usage history is connected.</span>
      </div>
    </section>
  )
}
