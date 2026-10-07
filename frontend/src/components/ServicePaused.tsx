import { ArrowRight, CirclePause } from 'lucide-react'

// Shown in place of a working Generate while the service is stopped for visitors.
export function ServicePaused({ onExamples }: { onExamples: () => void }) {
  return (
    <div className="service-paused" role="status">
      <CirclePause size={28} aria-hidden="true" />
      <h2>Service temporarily stopped by the developer</h2>
      <p>
        Live generation is off for now. The recorded examples show how a run
        works.
      </p>
      <button className="text-button" type="button" onClick={onExamples}>
        View examples
        <ArrowRight size={15} />
      </button>
    </div>
  )
}
