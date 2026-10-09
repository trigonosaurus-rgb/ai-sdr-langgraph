import { useEffect, useRef, useState } from 'react'
import { Pause, Play } from 'lucide-react'

const examples = [
  {
    id: 'workflow',
    title: 'Research to first draft',
    description:
      'A real run for Apollo: research and approach first, then the email streams in as it is written.',
    transcript:
      'Brief: Apollo (apollo.io), an offer of data enrichment quality audits, to the Head of Data, in English. Research kept 8 facts from Apollo’s site and help center, among them a database of 240M contacts and 30M companies used by 1 million sales professionals. The email ties that database to the audit and asks whether the team measures coverage and duplicate drift. It passed review as the first draft. The run took 22.9 seconds and cost about $0.04; in the recording, waits for the model are shortened.',
  },
  {
    id: 'evidence',
    title: 'Sources and approach',
    description:
      'Every fact has a verbatim quote and a link to its page; the approach keeps guesses apart from facts.',
    transcript:
      'Brief: Kontur (kontur.ru), an offer of AI triage for support requests, to the head of support, in Russian. Research kept 8 facts quoted from kontur.ru and its press pages, such as more than 3.1 million clients in 2025. Facts are summarised in English; quotes stay in the language of the source. The approach links the many product lines to the cost of routing requests by hand and marks three needs as unconfirmed hypotheses.',
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
              : 'Muted recording · real run'}
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
          Two real runs, replayed from their event logs. Stage times and costs
          are as measured; long waits for the model are shortened.
        </p>
      </div>
      {examples.map((example) => (
        <ExampleVideo key={example.id} example={example} />
      ))}
    </div>
  )
}
