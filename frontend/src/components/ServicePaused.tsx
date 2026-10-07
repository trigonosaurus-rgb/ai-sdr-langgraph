import { ArrowRight, CirclePause } from 'lucide-react'
import { monthDay } from '../format'

// Shown in place of a working Generate when this month's demo budget is used up.
export function ServicePaused({
  resumesAt,
  onExamples,
}: {
  resumesAt: string | null
  onExamples: () => void
}) {
  return (
    <div className="service-paused" role="status">
      <CirclePause size={28} aria-hidden="true" />
      <h2>Service paused by the developer</h2>
      <p>
        This month’s demo budget is used up, so live generation is off
        {resumesAt ? ` until ${monthDay(resumesAt)}` : ''}. The recorded
        examples show how a run works.
      </p>
      <button className="text-button" type="button" onClick={onExamples}>
        View examples
        <ArrowRight size={15} />
      </button>
    </div>
  )
}
