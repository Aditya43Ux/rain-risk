import { dayLabel } from '../lib/rain'

export default function DayStrip({ dates, day, onSelect, chanceByDate }) {
  return (
    <div role="tablist" aria-label="Forecast day" className="grid grid-cols-7 gap-1">
      {dates.map((d) => {
        const active = d === day
        const chance = chanceByDate?.[d]
        return (
          <button
            key={d}
            role="tab"
            aria-selected={active}
            onClick={() => onSelect(d)}
            className={`rounded-md px-1 py-2 text-center transition-colors ${
              active ? 'bg-ink text-white' : 'bg-mist hover:bg-line'
            }`}
          >
            <span className="block text-xs">{dayLabel(d)}</span>
            <span className="block text-base font-semibold leading-tight">
              {new Date(`${d}T00:00:00`).getDate()}
            </span>
            <span className={`block h-4 text-xs ${active ? 'text-white/80' : 'text-ink-soft'}`}>
              {chance == null ? '' : `${chance}%`}
            </span>
          </button>
        )
      })}
    </div>
  )
}
