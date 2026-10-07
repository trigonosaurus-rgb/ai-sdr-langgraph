import type { RunEvent } from './run'
import { steps } from './run'
import type { Brief } from './types'

// Mirrors core/schemas.py Brief. The server validates again; this only gives early, readable errors.
export const briefLimits = {
  company: 200,
  website: 500,
  offer: 2000,
  recipient: 200,
} as const
export type BriefErrors = Partial<Record<keyof Brief, string>>

export function domainOf(website: string): string {
  const value = website.trim()
  try {
    const url = new URL(value.includes('://') ? value : `https://${value}`)
    return url.hostname.toLowerCase().replace(/^www\./, '')
  } catch {
    return ''
  }
}

export function validateBrief(brief: Brief): BriefErrors {
  const errors: BriefErrors = {}
  const required: [keyof typeof briefLimits, string][] = [
    ['company', 'Enter the company name.'],
    ['website', 'Enter the company website.'],
    ['recipient', 'Enter the recipient role.'],
    ['offer', 'Describe your offer.'],
  ]
  for (const [field, message] of required) {
    const value = brief[field].trim()
    if (!value) errors[field] = message
    else if (value.length > briefLimits[field])
      errors[field] = `Keep it under ${briefLimits[field]} characters.`
  }
  if (!errors.website && !domainOf(brief.website).includes('.'))
    errors.website = 'Use a domain or URL, for example acme.com.'
  return errors
}

export interface RunSnapshot {
  runId: string
  status: 'running' | 'ready' | 'needs_attention' | 'failed'
  reason: string | null
  brief: Brief
  createdAt: string
  finishedAt: string | null
  lastSequence: number
}

// Mirrors server/store.py UsageTotals. Each total sums the calls that reported it; null means
// calls exist but none reported it, and `incomplete` means some did not.
export interface UsageTotals {
  runs: number
  llmCalls: number
  searchCalls: number
  input: number | null
  cachedInput: number | null // subset of input
  output: number | null
  reasoning: number | null // subset of output
  searchCredits: number | null
  modelUsd: number | null
  searchUsd: number | null
  durationSeconds: number | null
  models: string[]
  priceVersions: string[]
  incomplete: boolean
}
export interface LlmCallCost {
  stage: string
  attempt: number
  model: string
  input: number | null
  cachedInput: number | null
  output: number | null
  reasoning: number | null
  costUsd: number | null
  durationMs: number
  failed: boolean
}
export interface SearchCallCost {
  topic: string
  results: number
  credits: number | null
  costUsd: number | null
  durationMs: number
  failed: boolean
}
export interface RunCost {
  runId: string
  status: RunSnapshot['status']
  totals: UsageTotals
  llmCalls: LlmCallCost[]
  searchCalls: SearchCallCost[]
}
// The service's spending today, all visitors together.
export interface BudgetStatus {
  usd: number
  spentUsd: number
  searchCredits: number
  spentSearchCredits: number
  resetsAt: string
}
export interface PeriodUsage {
  period: '24h' | '30d'
  since: string
  totals: UsageTotals
  budget: BudgetStatus
}

// A request the server refused or could not serve; message is safe to show.
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly fieldErrors: BriefErrors = {},
  ) {
    super(message)
  }
}

const unavailable = 'The service is unavailable. Try again in a minute.'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(unavailable, 0)
  }
  const body: unknown = await response.json().catch(() => null)
  if (response.ok) return body as T
  throw errorFrom(response.status, body)
}

function errorFrom(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (status === 422 && Array.isArray(detail)) {
    // FastAPI validation errors: loc is ['body', field].
    const fieldErrors: BriefErrors = {}
    for (const item of detail as { loc?: unknown[]; msg?: string }[]) {
      const field = item.loc?.[1]
      if (typeof field === 'string' && field in briefLimits)
        fieldErrors[field as keyof Brief] = item.msg ?? 'Check this field.'
    }
    return new ApiError('Check the highlighted fields.', status, fieldErrors)
  }
  if (typeof detail === 'string' && status < 500)
    return new ApiError(detail, status)
  return new ApiError(unavailable, status)
}

export const api = {
  health: () => request<{ status: string }>('/api/health'),
  createRun: (brief: Brief) =>
    request<{ runId: string }>('/api/runs', {
      method: 'POST',
      body: JSON.stringify(brief),
    }),
  getRun: (runId: string) =>
    request<RunSnapshot>(`/api/runs/${encodeURIComponent(runId)}`),
  runUsage: (runId: string) =>
    request<RunCost>(`/api/runs/${encodeURIComponent(runId)}/usage`),
  usage: (period: PeriodUsage['period']) =>
    request<PeriodUsage>(`/api/usage?period=${period}`),
  cancelRun: (runId: string) =>
    request<{ runId: string }>(
      `/api/runs/${encodeURIComponent(runId)}/cancel`,
      { method: 'POST' },
    ),
}

// --- Runtime validation of streamed events: the reducer trusts their shape.

type Shape = Record<string, (value: unknown) => boolean>
const isString = (value: unknown) => typeof value === 'string'
const isInt = (value: unknown) => Number.isInteger(value)
const isBool = (value: unknown) => typeof value === 'boolean'
const isStrings = (value: unknown) =>
  Array.isArray(value) && value.every(isString)
const optional = (check: (value: unknown) => boolean) => (value: unknown) =>
  value == null || check(value)
const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)
const oneOf =
  (...options: unknown[]) =>
  (value: unknown) =>
    options.includes(value)
const isStage = oneOf(...steps)
const isSource = (value: unknown) =>
  isObject(value) &&
  isInt(value.id) &&
  ['claim', 'title', 'url', 'path', 'excerpt'].every((key) =>
    isString(value[key]),
  )

const shapes: Record<RunEvent['type'], Shape> = {
  started: { company: isString, recipient: isString },
  stage: { stage: isStage, message: isString, elapsedMs: optional(isInt) },
  activity: { message: isString },
  evidence: {
    sources: (value) => Array.isArray(value) && value.every(isSource),
  },
  strategy: {
    strategy: (value) =>
      isObject(value) &&
      isStrings(value.hypotheses) &&
      Array.isArray(value.factIds) &&
      oneOf('good', 'weak', 'poor')(value.offerFit) &&
      ['observation', 'offerLink', 'angle', 'fitReason'].every((key) =>
        isString(value[key]),
      ),
  },
  draft_reset: { attempt: isInt },
  draft_delta: { field: oneOf('subject', 'body'), delta: isString },
  review: { attempt: isInt, passed: isBool, issues: isStrings },
  completed: {
    outcome: oneOf('ready', 'needs_attention'),
    issues: isStrings,
    usage: (value) => value === null || isObject(value),
    elapsedMs: optional(isInt),
  },
  failed: {
    reason: oneOf(
      'insufficient_data',
      'website_mismatch',
      'cancelled',
      'daily_limit',
      'error',
    ),
    message: isString,
    stage: optional(isStage),
    elapsedMs: optional(isInt),
  },
}

export function parseEvent(data: unknown): RunEvent | null {
  if (!isObject(data) || !isString(data.runId) || !isInt(data.sequence))
    return null
  const shape = shapes[data.type as RunEvent['type']]
  if (!shape) return null
  return Object.entries(shape).every(([key, check]) => check(data[key]))
    ? (data as unknown as RunEvent)
    : null
}

export type StreamStatus = 'connecting' | 'live' | 'reconnecting' | 'closed'

// Follows one run's event stream from `after`. EventSource reconnects by itself and resumes
// with Last-Event-ID; events from any other run or with a malformed shape are dropped here,
// before the reducer. The stream is closed after the terminal event.
export function followRun(
  runId: string,
  after: number,
  handlers: {
    onEvent: (event: RunEvent) => void
    onStatus: (status: StreamStatus) => void
  },
): () => void {
  handlers.onStatus('connecting')
  const source = new EventSource(
    `/api/runs/${encodeURIComponent(runId)}/events?after=${after}`,
  )
  source.onopen = () => handlers.onStatus('live')
  source.onerror = () =>
    handlers.onStatus(
      source.readyState === EventSource.CLOSED ? 'closed' : 'reconnecting',
    )
  source.onmessage = (message: MessageEvent<string>) => {
    let event: RunEvent | null = null
    try {
      event = parseEvent(JSON.parse(message.data))
    } catch {
      event = null
    }
    if (!event || event.runId !== runId) return
    handlers.onEvent(event)
    if (event.type === 'completed' || event.type === 'failed') {
      source.close()
      handlers.onStatus('closed')
    }
  }
  return () => source.close()
}
