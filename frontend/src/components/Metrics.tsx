import { CircleAlert, Coins, Layers3, Timer } from 'lucide-react'
import { useEffect, useState } from 'react'
import { CostPeriodControl } from './CostPeriodControl'
import type { CostPeriod } from './CostPeriodControl'
import { api } from '../api'
import type {
  ApiError,
  BudgetStatus,
  LlmCallCost,
  PeriodUsage,
  RunCost,
  UsageTotals,
} from '../api'
import type { RunState } from '../run'

const number = (value: number | null | undefined) =>
  value == null ? '—' : value.toLocaleString('en-US')
const money = (value: number | null | undefined) =>
  value == null ? '—' : `$${value.toFixed(4)}`
const seconds = (value: number | null | undefined) =>
  value == null
    ? '—'
    : value.toLocaleString('en-US', {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })
const dollars = (value: number) => `$${value.toFixed(2)}`
const sum = (a: number | null | undefined, b: number | null | undefined) =>
  a != null && b != null ? a + b : null
const plural = (count: number, word: string) =>
  `${count.toLocaleString('en-US')} ${word}${count === 1 ? '' : 's'}`
const periodName = { '24h': '24 hours', '30d': '30 days' } as const

type Loaded =
  | { view: string; data: RunCost | PeriodUsage }
  | { view: string; error: string }

// Fetches the selected view, and again whenever `refresh` changes: the server stores each
// paid call as it ends, so a run's usage grows while it runs. Data of the same view stays
// up during a refetch; another view's data is never shown.
function useUsage(period: CostPeriod, runId: string | null, refresh: string) {
  const view = period === 'run' ? `run:${runId}` : period
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  useEffect(() => {
    let request: Promise<RunCost | PeriodUsage>
    if (period !== 'run') request = api.usage(period)
    else if (runId) request = api.runUsage(runId)
    else return
    let alive = true
    request.then(
      (data) => alive && setLoaded({ view, data }),
      (failure: ApiError) =>
        alive && setLoaded({ view, error: failure.message }),
    )
    return () => {
      alive = false
    }
  }, [period, runId, view, refresh])
  return loaded?.view === view ? loaded : null
}

function stepName(call: LlmCallCost) {
  const draft =
    call.attempt > 1 && (call.stage === 'Writing' || call.stage === 'Review')
      ? `, draft ${call.attempt}`
      : ''
  return `${call.stage}${draft}${call.failed ? ' (failed)' : ''}`
}

function StepTable({ cost }: { cost: RunCost }) {
  const searches = cost.searchCalls
  if (!searches.length && !cost.llmCalls.length) return null
  const credits = searches.every((call) => call.credits != null)
    ? searches.reduce((total, call) => total + (call.credits ?? 0), 0)
    : null
  const searchUsd = searches.every((call) => call.costUsd != null)
    ? searches.reduce((total, call) => total + (call.costUsd ?? 0), 0)
    : null
  return (
    <div className="cost-steps">
      <span className="label-small" id="cost-steps-title">
        By step
      </span>
      <table aria-labelledby="cost-steps-title">
        <thead>
          <tr>
            <th scope="col">Step</th>
            <th scope="col">Tokens in / out</th>
            <th scope="col">Cost</th>
          </tr>
        </thead>
        <tbody>
          {searches.length > 0 && (
            <tr>
              <th scope="row">
                Web search, {plural(searches.length, 'request')}
              </th>
              <td>{credits == null ? '—' : plural(credits, 'credit')}</td>
              <td>{money(searchUsd)}</td>
            </tr>
          )}
          {cost.llmCalls.map((call, index) => (
            <tr key={index} className={call.failed ? 'failed' : undefined}>
              <th scope="row">{stepName(call)}</th>
              <td>
                {number(call.input)} / {number(call.output)}
              </td>
              <td>{money(call.costUsd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function budgetLine(budget: BudgetStatus) {
  return `Service budget this month: ${dollars(budget.spentModelUsd)} of ${dollars(budget.modelUsd)} for models and ${number(budget.spentSearchCredits)} of ${number(budget.searchCredits)} search credits, shared by all visitors.`
}

export function Metrics({
  runId,
  runStatus = 'idle',
  runStage = null,
}: {
  runId: string | null
  runStatus?: RunState['status']
  runStage?: RunState['stage']
}) {
  const [period, setPeriod] = useState<CostPeriod>('run')
  const loaded = useUsage(period, runId, `${runStatus}:${runStage}`)
  const data = loaded && 'data' in loaded ? loaded.data : null
  const totals: UsageTotals | null = data?.totals ?? null
  const runCost = data && 'llmCalls' in data ? data : null
  const budget = data && 'budget' in data ? data.budget : null
  const running = period === 'run' && runStatus === 'running'

  let intro: string
  if (period === 'run' && !runId)
    intro =
      'No run yet. Actual usage will appear here after your first generation.'
  else if (loaded && 'error' in loaded) intro = loaded.error
  else if (!totals) intro = 'Loading usage…'
  else if (period === 'run')
    intro = running
      ? 'This run is in progress; totals grow as each call finishes. Amounts are estimates in USD.'
      : 'Usage for this run. Amounts are estimates in USD.'
  else
    intro = totals.runs
      ? `${plural(totals.runs, 'run')} from your address over the last ${periodName[period]}. Amounts are estimates in USD.`
      : `No runs from your address over the last ${periodName[period]}.`

  return (
    <section
      className="usage-section"
      aria-label="Usage details"
      aria-busy={!loaded && !(period === 'run' && !runId)}
    >
      <CostPeriodControl value={period} onChange={setPeriod} />
      <p className="costs-intro" role="status">
        {intro}
      </p>
      {totals?.incomplete && (
        <p className="cost-note">
          <CircleAlert size={15} aria-hidden="true" />
          Incomplete data: some calls did not report usage or have no price.
          Totals cover only what was reported.
        </p>
      )}
      <div className="metrics-grid">
        <div className="metric">
          <span className="metric-label">
            <Coins size={15} />
            Estimated cost
          </span>
          <strong>
            {money(sum(totals?.modelUsd, totals?.searchUsd))}
            <span> USD</span>
          </strong>
          <span className="muted">Model + search</span>
        </div>
        <div className="metric">
          <span className="metric-label">
            <Layers3 size={15} />
            Total tokens
          </span>
          <strong>{number(sum(totals?.input, totals?.output))}</strong>
          <span className="muted">Input + output</span>
        </div>
        <div className="metric">
          <span className="metric-label">
            <Timer size={15} />
            {period === 'run' ? 'Duration' : 'Total runtime'}
          </span>
          <strong>
            {seconds(totals?.durationSeconds)}
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
          <dd>{number(totals?.input)}</dd>
        </div>
        <div className="subset">
          <dt>Of which cached</dt>
          <dd>{number(totals?.cachedInput)}</dd>
        </div>
        <div>
          <dt>Output tokens</dt>
          <dd>{number(totals?.output)}</dd>
        </div>
        <div className="subset">
          <dt>Of which reasoning</dt>
          <dd>{number(totals?.reasoning)}</dd>
        </div>
        <div>
          <dt>Model cost</dt>
          <dd>{money(totals?.modelUsd)}</dd>
        </div>
        <div>
          <dt>
            Search cost
            {totals ? `, ${plural(totals.searchCalls, 'request')}` : ''}
          </dt>
          <dd>{money(totals?.searchUsd)}</dd>
        </div>
      </dl>
      {runCost && <StepTable cost={runCost} />}
      <p className="fine-print">
        {totals?.models.length ? `Model: ${totals.models.join(', ')}. ` : ''}
        {totals?.priceVersions.length
          ? `Prices as of ${totals.priceVersions.join(', ')}: OpenAI list prices, web search at the Tavily pay-as-you-go rate. `
          : ''}
        Cached input and reasoning are included in their respective totals,
        never counted twice. A dash means the value is unavailable.
      </p>
      <div className="costs-bottom">
        <span>Estimated usage, not an invoice.</span>
        {budget && <span>{budgetLine(budget)}</span>}
      </div>
    </section>
  )
}
