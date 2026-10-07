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
import { RunPanel } from './components/RunPanel'
import { RunTimeline } from './components/RunTimeline'
import { Examples } from './components/Examples'
import { emptyBrief, emptyRun } from './run'

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
  function newBrief() {
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
              <BriefForm brief={brief} onChange={setBrief} />
              <RunPanel
                run={emptyRun}
                onExamples={() => navigate('examples')}
              />
              <RunTimeline run={emptyRun} onCosts={() => setModal('costs')} />
            </div>
          )}
        </main>
      </div>
      {modal === 'costs' && (
        <Modal title="Run costs" onClose={() => setModal(null)} wide>
          <Metrics usage={null} />
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
                <strong>Local development</strong>The live generation service is
                not connected to this interface yet. Filling in a brief makes no
                API calls and uses no credits.
              </p>
            </div>
            <div>
              <BookOpen size={18} />
              <p>
                <strong>Recorded walkthroughs</strong>The Examples page contains
                short recordings made with fictional company data. They show the
                intended workflow, including incremental writing.
              </p>
            </div>
            <div>
              <Wallet size={18} />
              <p>
                <strong>Usage and access</strong>Actual token usage, cost
                estimates and trial access will be supplied by the server. No
                trial runs are available or deducted in this local interface.
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
