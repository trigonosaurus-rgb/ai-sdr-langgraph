import { useRef } from 'react'
import type { CSSProperties, KeyboardEvent } from 'react'

export const costPeriods = [
  { id: '30d', label: '30 days' },
  { id: '24h', label: '24 hours' },
  { id: 'run', label: 'This run' },
] as const
export type CostPeriod = (typeof costPeriods)[number]['id']

export function CostPeriodControl({
  value,
  onChange,
}: {
  value: CostPeriod
  onChange: (value: CostPeriod) => void
}) {
  const drag = useRef<{ start: number; moved: boolean } | null>(null)
  const index = costPeriods.findIndex((period) => period.id === value)
  function keyboard(event: KeyboardEvent<HTMLButtonElement>) {
    const next =
      event.key === 'ArrowRight' || event.key === 'ArrowDown'
        ? (index + 1) % 3
        : event.key === 'ArrowLeft' || event.key === 'ArrowUp'
          ? (index + 2) % 3
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? 2
              : -1
    if (next < 0) return
    event.preventDefault()
    onChange(costPeriods[next].id)
    event.currentTarget.parentElement
      ?.querySelectorAll<HTMLButtonElement>('button')
      [next].focus()
  }
  return (
    <div
      className="cost-period-control"
      role="radiogroup"
      aria-label="Usage period"
      style={{ '--period-index': index } as CSSProperties}
      onPointerDown={(event) => {
        if (event.button !== 0) return
        drag.current = { start: event.clientX, moved: false }
      }}
      onPointerMove={(event) => {
        if (!drag.current) return
        if (
          Math.abs(event.clientX - drag.current.start) < 8 &&
          !drag.current.moved
        )
          return
        drag.current.moved = true
        event.currentTarget.setPointerCapture(event.pointerId)
        const rect = event.currentTarget.getBoundingClientRect()
        const next = Math.max(
          0,
          Math.min(
            2,
            Math.floor((event.clientX - rect.left) / (rect.width / 3)),
          ),
        )
        onChange(costPeriods[next].id)
      }}
      onPointerUp={() => {
        drag.current = null
      }}
      onPointerLeave={() => {
        if (!drag.current?.moved) drag.current = null
      }}
      onPointerCancel={() => {
        drag.current = null
      }}
      onLostPointerCapture={() => {
        drag.current = null
      }}
    >
      <span className="cost-period-thumb" aria-hidden="true" />
      {costPeriods.map((period) => (
        <button
          key={period.id}
          type="button"
          role="radio"
          aria-checked={value === period.id}
          tabIndex={value === period.id ? 0 : -1}
          onClick={() => onChange(period.id)}
          onKeyDown={keyboard}
        >
          {period.label}
        </button>
      ))}
    </div>
  )
}
