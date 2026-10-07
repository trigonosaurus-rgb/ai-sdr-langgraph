import { vi } from 'vitest'
import type { RunEvent } from '../run'

// Minimal EventSource double: tests push events into the stream a component opened.
export class FakeEventSource {
  static instances: FakeEventSource[] = []
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSED = 2
  readyState = FakeEventSource.CONNECTING
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  onmessage: ((message: MessageEvent<string>) => void) | null = null
  constructor(readonly url: string) {
    FakeEventSource.instances.push(this)
  }
  open() {
    this.readyState = FakeEventSource.OPEN
    this.onopen?.()
  }
  send(...events: (RunEvent | Record<string, unknown>)[]) {
    for (const event of events)
      this.onmessage?.(
        new MessageEvent('message', { data: JSON.stringify(event) }),
      )
  }
  close() {
    this.readyState = FakeEventSource.CLOSED
  }
  static latest() {
    return FakeEventSource.instances.at(-1)!
  }
}

type Reply = { status?: number; body?: unknown }
type Route = (init?: RequestInit) => Reply

// A fetch double keyed by "METHOD /path"; unknown routes fail like a network error.
export function mockApi(routes: Record<string, Route | Reply>) {
  const fetch = vi.fn(async (input: string, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${input}`
    const route = routes[key]
    if (!route) throw new TypeError(`Failed to fetch ${key}`)
    const reply = typeof route === 'function' ? route(init) : route
    return new Response(JSON.stringify(reply.body ?? null), {
      status: reply.status ?? 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

export const online = { 'GET /api/health': { body: { status: 'ok' } } }
