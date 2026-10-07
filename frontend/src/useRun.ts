import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import { ApiError, api, followRun } from './api'
import type { ServiceStatus, StreamStatus } from './api'
import { emptyRun, reduceRun } from './run'
import type { RunEvent, RunState } from './run'
import type { Brief } from './types'

// The run shown in the workspace survives a reload: its id is kept until New outreach,
// and the view is rebuilt by replaying the run's events from the server.
const ACTIVE_RUN_KEY = 'ai-sdr.active-run.v1'

function readSaved(): string | null {
  try {
    return localStorage.getItem(ACTIVE_RUN_KEY)
  } catch {
    return null
  }
}
function save(runId: string | null) {
  try {
    if (runId) localStorage.setItem(ACTIVE_RUN_KEY, runId)
    else localStorage.removeItem(ACTIVE_RUN_KEY)
  } catch {
    // Storage blocked: the run still works, it just is not restored after a reload.
  }
}

type Action = RunEvent | { type: 'reset' }
const reducer = (state: RunState, action: Action) =>
  action.type === 'reset' ? emptyRun : reduceRun(state, action)

export type ServiceState = 'checking' | 'online' | 'offline'
export type RunSession = ReturnType<typeof useRun>
const HEALTH_RETRY_MS = 15_000

export function useRun(onRestore: (brief: Brief) => void) {
  const [run, dispatch] = useReducer(reducer, emptyRun)
  const [service, setService] = useState<ServiceState>('checking')
  // The service's budget and this visitor's quota; refreshed when a run ends or a start is refused.
  const [status, setStatus] = useState<ServiceStatus | null>(null)
  const [stream, setStream] = useState<StreamStatus>('closed')
  // The run this tab started or restored; until its `started` event arrives it is "starting".
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [requesting, setRequesting] = useState(false)
  const [cancelRequested, setCancelRequested] = useState<string | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const close = useRef<(() => void) | null>(null)
  const restore = useRef(onRestore)
  useEffect(() => {
    restore.current = onRestore
  })

  const follow = useCallback((runId: string) => {
    close.current?.()
    setCurrentId(runId)
    close.current = followRun(runId, -1, {
      onEvent: dispatch,
      onStatus: setStream,
    })
  }, [])

  const checkService = useCallback(() => {
    let alive = true
    api.status().then(
      (next) => {
        if (!alive) return
        setStatus(next)
        setService('online')
      },
      () => alive && setService('offline'),
    )
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    let alive = true
    const stopCheck = checkService()
    const saved = readSaved()
    if (saved)
      api.getRun(saved).then(
        (snapshot) => {
          if (!alive) return
          restore.current(snapshot.brief)
          follow(saved)
        },
        (failure: ApiError) => {
          if (alive && failure.status === 404) save(null)
        },
      )
    return () => {
      alive = false
      stopCheck()
      close.current?.()
    }
  }, [follow, checkService])

  // While the service is down, check again now and then so Generate comes back by itself.
  useEffect(() => {
    if (service !== 'offline') return
    const timer = window.setInterval(checkService, HEALTH_RETRY_MS)
    return () => window.clearInterval(timer)
  }, [service, checkService])

  // A finished run uses up quota and budget; a run stopped by the budget pauses the service.
  const finished = run.id !== null && run.status !== 'running'
  useEffect(() => {
    if (finished) return checkService()
  }, [finished, run.id, checkService])

  const starting =
    requesting ||
    (currentId !== null && run.id !== currentId && stream !== 'closed')
  const running = run.status === 'running'

  async function start(brief: Brief) {
    setError(null)
    setRequesting(true)
    try {
      const { runId } = await api.createRun(brief)
      save(runId)
      follow(runId)
    } catch (failure) {
      setError(failure as ApiError)
      if ((failure as ApiError).status === 429) checkService()
    } finally {
      setRequesting(false)
    }
  }

  async function cancel() {
    if (!run.id || !running) return
    setCancelRequested(run.id)
    try {
      await api.cancelRun(run.id)
    } catch (failure) {
      // 409: the run finished first; its outcome arrives in the stream.
      if ((failure as ApiError).status !== 409) {
        setCancelRequested(null)
        setError(failure as ApiError)
      }
    }
  }

  // New outreach: stop following, stop spending on a run still in progress, forget it.
  function reset() {
    if (running && run.id) api.cancelRun(run.id).catch(() => undefined)
    close.current?.()
    close.current = null
    save(null)
    setCurrentId(null)
    setCancelRequested(null)
    setError(null)
    setStream('closed')
    dispatch({ type: 'reset' })
  }

  return {
    run,
    service,
    status,
    error,
    starting,
    running,
    cancelling: running && cancelRequested === run.id,
    // The stream dropped before the run ended: EventSource is retrying, or gave up.
    connection: running ? stream : 'live',
    // The run could not be opened at all (the stream was refused before `started`).
    lostRun:
      currentId !== null &&
      run.id !== currentId &&
      stream === 'closed' &&
      !requesting,
    start,
    cancel,
    reset,
  }
}
