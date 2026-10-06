import { useEffect, useRef, useState } from 'react'
import { Pause, Play } from 'lucide-react'

const examples = [
  {
    id: 'workflow',
    title: 'Research to first draft',
    description:
      'Research and approach run first, then the email streams in as it is written.',
    transcript:
      'Northstar is a fictional software company with guided onboarding. The research supplies company context; the approach connects it to workflow automation. The draft asks whether the team has manual steps when handing customers from sales to onboarding. It does not claim a confirmed problem.',
  },
  {
    id: 'evidence',
    title: 'Sources and approach',
    description:
      'Each claim in the draft can be checked against a source excerpt before you send it.',
    transcript:
      'The research tab contains three prepared Northstar excerpts: the product, guided onboarding and integrations. The approach labels a manual handoff as a hypothesis to explore, not an established fact.',
  },
]

function ExampleVideo({ example }: { example: (typeof examples)[number] }) {
  const ref = useRef<HTMLVideoElement>(null)
  const [playing, setPlaying] = useState(false)
  const [failed, setFailed] = useState(false)
  const pausedByUser = useRef(false)
  useEffect(() => {
    const video = ref.current!
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)')
    let visible = false
    function sync() {
      if (
        visible &&
        !document.hidden &&
        !reduced.matches &&
        !pausedByUser.current
      )
        void video.play().catch(() => setPlaying(false))
      else video.pause()
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting
        sync()
      },
      { threshold: 0.25 },
    )
    observer.observe(video)
    reduced.addEventListener('change', sync)
    document.addEventListener('visibilitychange', sync)
    return () => {
      observer.disconnect()
      reduced.removeEventListener('change', sync)
      document.removeEventListener('visibilitychange', sync)
      video.pause()
    }
  }, [])
  function toggle() {
    const video = ref.current!
    if (video.paused) {
      pausedByUser.current = false
      void video.play().catch(() => setPlaying(false))
    } else {
      pausedByUser.current = true
      video.pause()
    }
  }
  return (
    <article className="example-story">
      <div className="example-copy">
        <h2>{example.title}</h2>
        <p>{example.description}</p>
      </div>
      <div className="example-film">
        <video
          ref={ref}
          muted
          loop
          playsInline
          preload="metadata"
          poster={`/examples/${example.id}.png`}
          aria-label={example.title}
          aria-describedby={`transcript-${example.id}`}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onError={() => setFailed(true)}
        >
          <source src={`/examples/${example.id}.webm`} type="video/webm" />
        </video>
        <div className="video-caption">
          <span>
            {failed
              ? 'Video unavailable. Read the walkthrough below.'
              : 'Muted recording · fictional data'}
          </span>
          <button
            className="video-toggle"
            onClick={toggle}
            disabled={failed}
            aria-label={`${playing ? 'Pause' : 'Play'} ${example.title}`}
          >
            {playing ? <Pause size={14} /> : <Play size={14} />}
            {playing ? 'Pause' : 'Play'}
          </button>
        </div>
        <details className="video-transcript" id={`transcript-${example.id}`}>
          <summary>Read walkthrough</summary>
          <p>{example.transcript}</p>
        </details>
      </div>
    </article>
  )
}

export function Examples() {
  return (
    <div className="examples-page">
      <div className="page-heading">
        <h1>Examples</h1>
        <p>
          Two recorded runs with a fictional company, Northstar. They show the
          intended flow; live generation is not connected yet.
        </p>
      </div>
      {examples.map((example) => (
        <ExampleVideo key={example.id} example={example} />
      ))}
    </div>
  )
}
