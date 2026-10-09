import { useEffect, useRef, useState } from 'react'
import {
  ArrowRight,
  BookOpen,
  CircleHelp,
  ExternalLink,
  LayoutDashboard,
  PanelLeftClose,
  Plus,
  Wallet,
  X,
} from 'lucide-react'
import { ThemeControl } from './components/ThemeControl'
import { Modal } from './components/Modal'
import { Metrics } from './components/Metrics'
import { BriefForm } from './components/BriefForm'
import type { FormStatus } from './components/BriefForm'
import { RunPanel } from './components/RunPanel'
import { RunTimeline } from './components/RunTimeline'
import { Examples } from './components/Examples'
import { ServicePaused } from './components/ServicePaused'
import { when } from './format'
import { emptyBrief } from './run'
import { validateBrief } from './api'
import type { BriefErrors } from './api'
import { useRun } from './useRun'
import type { RunSession } from './useRun'

function formStatus(session: RunSession): FormStatus {
  if (session.error) return { tone: 'error', text: session.error.message }
  if (session.lostRun)
    return {
      tone: 'error',
      text: 'Could not open the run. Reload the page to try again.',
    }
  if (session.running) {
    if (session.connection === 'closed')
      return {
        tone: 'error',
        text: 'Lost connection to the run. Reload the page to resume it.',
      }
    if (session.connection === 'reconnecting')
      return { tone: 'working', text: 'Connection lost. Reconnecting…' }
    return {
      tone: 'working',
      text: session.cancelling
        ? 'Stopping before the next paid call…'
        : 'Running on the server. Reloading the page keeps it.',
    }
  }
  if (session.service === 'checking')
    return { tone: 'working', text: 'Checking the service…' }
  if (session.service === 'offline')
    return {
      tone: 'offline',
      text: 'The service is unavailable, so generation is off.',
    }
  const status = session.status
  if (status?.developer)
    return {
      tone: 'online',
      text: `Developer access: no limits.${status.paused ? ' The service is stopped for visitors.' : ''}`,
    }
  if (status?.paused)
    return {
      tone: 'offline',
      text: 'Temporarily stopped by the developer.',
    }
  const visitor = status?.visitor
  if (visitor?.nextRunAt) {
    const period =
      visitor.runsToday >= visitor.runsPerDay
        ? `your ${visitor.runsPerDay} runs for today`
        : `your ${visitor.runsPerMonth} runs for this month`
    return {
      tone: 'offline',
      text: `You have used ${period}. The next run is available ${when(visitor.nextRunAt)}.`,
    }
  }
  const left = visitor
    ? ` Runs left: ${Math.min(visitor.runsPerDay - visitor.runsToday, visitor.runsPerMonth - visitor.runsThisMonth)} today, ${visitor.runsPerMonth - visitor.runsThisMonth} this month.`
    : ''
  return {
    tone: 'online',
    text: `Each run makes real model and search calls.${left}`,
  }
}

function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 40 40" aria-hidden="true">
      <rect width="40" height="40" rx="9" />
      <path
        d="M14 26 26 14M17 14h9v9"
        fill="none"
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function currentPage() {
  return location.hash === '#examples' ? 'examples' : 'compose'
}

export default function App() {
  const [page, setPage] = useState(currentPage)
  const [brief, setBrief] = useState(emptyBrief)
  const [showErrors, setShowErrors] = useState(false)
  const session = useRun(setBrief)
  const errors: BriefErrors = {
    ...session.error?.fieldErrors,
    ...(showErrors ? validateBrief(brief) : {}),
  }
  const [modal, setModal] = useState<'costs' | 'guide' | null>(null)
  const [mobileNav, setMobileNav] = useState(false)
  const mainRef = useRef<HTMLElement>(null)
  const navRef = useRef<HTMLElement>(null)
  const menuRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const change = () => {
      setPage(currentPage())
      setModal(null)
      setMobileNav(false)
      mainRef.current?.focus()
    }
    window.addEventListener('hashchange', change)
    return () => window.removeEventListener('hashchange', change)
  }, [])
  useEffect(() => {
    if (!mobileNav) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    navRef.current?.querySelector<HTMLButtonElement>('.mobile-close')?.focus()
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileNav(false)
      if (event.key !== 'Tab') return
      const items = Array.from(
        navRef.current?.querySelectorAll<HTMLElement>(
          'a, button:not(:disabled)',
        ) ?? [],
      ).filter((item) => item.getClientRects().length)
      const first = items[0],
        last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last?.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first?.focus()
      }
    }
    document.addEventListener('keydown', keydown)
    return () => {
      document.body.style.overflow = previous
      document.removeEventListener('keydown', keydown)
      menuRef.current?.focus()
    }
  }, [mobileNav])
  function navigate(next: 'compose' | 'examples') {
    location.hash = next
    setPage(next)
    setMobileNav(false)
  }
  function generate() {
    const found = Object.keys(validateBrief(brief))
    if (found.length) {
      setShowErrors(true)
      document.getElementById(found[0])?.focus()
      return
    }
    setShowErrors(false)
    session.start(brief)
  }
  function newBrief() {
    session.reset()
    setShowErrors(false)
    setBrief({ ...emptyBrief })
    navigate('compose')
    requestAnimationFrame(() => document.getElementById('company')?.focus())
  }
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to workspace
      </a>
      {mobileNav && (
        <button
          className="nav-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobileNav(false)}
        />
      )}
      <aside
        ref={navRef}
        className={`sidebar ${mobileNav ? 'is-open' : ''}`}
        aria-label="Workspace navigation"
      >
        <a
          className="brand"
          href="#compose"
          onClick={() => navigate('compose')}
        >
          <BrandMark />
          AI SDR
        </a>
        <button
          className="mobile-close icon-button"
          aria-label="Close navigation"
          onClick={() => setMobileNav(false)}
        >
          <X size={20} />
        </button>
        <button className="new-button" onClick={newBrief}>
          <Plus size={16} />
          New outreach
        </button>
        <nav>
          <a
            className={`nav-item ${page === 'compose' ? 'active' : ''}`}
            href="#compose"
            aria-current={page === 'compose' ? 'page' : undefined}
            onClick={() => navigate('compose')}
          >
            <LayoutDashboard size={18} />
            Compose
          </a>
          <a
            className={`nav-item ${page === 'examples' ? 'active' : ''}`}
            href="#examples"
            aria-current={page === 'examples' ? 'page' : undefined}
            onClick={() => navigate('examples')}
          >
            <BookOpen size={18} />
            Examples
          </a>
          <button
            className="nav-item"
            onClick={() => {
              setMobileNav(false)
              setModal('costs')
            }}
            aria-haspopup="dialog"
          >
            <Wallet size={18} />
            Run costs
          </button>
        </nav>
        <div className="sidebar-bottom">
          <button
            className="sidebar-help"
            onClick={() => {
              setMobileNav(false)
              setModal('guide')
            }}
          >
            <CircleHelp size={16} />
            About
          </button>
          <a
            className="repo-link"
            href="https://github.com/trigonosaurus-rgb/ai-sdr-langgraph"
            target="_blank"
            rel="noreferrer"
          >
            <ExternalLink size={16} />
            Source on GitHub
          </a>
          <div className="sidebar-theme">
            <ThemeControl />
          </div>
        </div>
      </aside>
      <div className="main-shell" inert={mobileNav}>
        <header className="topbar">
          <div className="topbar-start">
            <button
              ref={menuRef}
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              aria-expanded={mobileNav}
              onClick={() => setMobileNav(true)}
            >
              <PanelLeftClose size={20} />
            </button>
            <span className="brand">
              <BrandMark />
              AI SDR
            </span>
          </div>
        </header>
        <main id="main" tabIndex={-1} ref={mainRef}>
          {page === 'examples' ? (
            <Examples />
          ) : (
            <div className="workspace">
              <h1 className="sr-only">Compose outreach</h1>
              <BriefForm
                brief={brief}
                onChange={setBrief}
                errors={errors}
                locked={session.running || session.starting}
                running={session.running}
                starting={session.starting}
                cancelling={session.cancelling}
                canGenerate={
                  session.service === 'online' &&
                  (!!session.status?.developer ||
                    (!session.status?.paused &&
                      !session.status?.visitor.nextRunAt))
                }
                status={formStatus(session)}
                notice={
                  session.service === 'online' &&
                  session.status?.paused &&
                  !session.status.developer && (
                    <ServicePaused onExamples={() => navigate('examples')} />
                  )
                }
                onGenerate={generate}
                onCancel={session.cancel}
              />
              <RunPanel
                run={session.run}
                paused={session.status?.paused && !session.status.developer}
                onExamples={() => navigate('examples')}
              />
              <RunTimeline
                run={session.run}
                onCosts={() => setModal('costs')}
              />
            </div>
          )}
        </main>
      </div>
      {modal === 'costs' && (
        <Modal title="Run costs" onClose={() => setModal(null)} wide>
          <Metrics
            runId={session.run.id}
            runStatus={session.run.status}
            runStage={session.run.stage}
          />
        </Modal>
      )}
      {modal === 'guide' && (
        <Modal title="About this workspace" onClose={() => setModal(null)}>
          <p>
            Research a company, connect your offer to the evidence and review a
            short outreach draft before using it.
          </p>
          <div className="guide-list">
            <div>
              <CircleHelp size={18} />
              <p>
                <strong>Live generation</strong>Generate researches the company
                with real web search and model calls on the server.{' '}
                {session.status
                  ? `Each visitor gets ${session.status.visitor.runsPerDay} runs a day and ${session.status.visitor.runsPerMonth} a month, one at a time.`
                  : 'Each visitor gets a few runs a day, one at a time.'}{' '}
                Nothing is sent for you.
              </p>
            </div>
            <div>
              <BookOpen size={18} />
              <p>
                <strong>Recorded walkthroughs</strong>The Examples page replays
                two real runs, with the email written as it streams and every
                fact traced to its source.
              </p>
            </div>
            <div>
              <Wallet size={18} />
              <p>
                <strong>Usage</strong>Token counts come from the provider's
                response metadata; costs are estimated from list prices when
                each call is recorded. Anything not reported shows as unknown,
                not zero. The service has a monthly budget; when it is used up,
                generation pauses until the next month.
              </p>
            </div>
          </div>
          <button
            className="primary-button"
            onClick={() => {
              setModal(null)
              navigate('examples')
            }}
          >
            View examples
            <ArrowRight size={16} />
          </button>
        </Modal>
      )}
    </div>
  )
}
