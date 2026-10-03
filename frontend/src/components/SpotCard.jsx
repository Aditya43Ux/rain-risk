import { coords, dayLabel, mm, rainColor, rainWords } from '../lib/rain'

export default function SpotCard({ place, day, today, thresholdMm, error, onShowArea }) {
  if (error) {
    return (
      <div className="rounded-2xl bg-white p-5">
        <p className="font-semibold">{place.name ?? coords(place)}</p>
        <p className="mt-1 text-sm text-ink-soft">{error}</p>
        <button type="button" onClick={onShowArea} className="mt-3 rounded-full bg-mist px-3 py-1.5 text-sm font-medium hover:bg-line">
          Show the forecast area
        </button>
      </div>
    )
  }

  const pct = today?.chance_pct
  return (
    <div className="overflow-hidden rounded-2xl bg-white">
      <div className="h-1.5" style={{ background: rainColor(pct) }} />
      <div className="p-5">
        <p className="font-semibold">{place.name ?? 'Pinned spot'}</p>
        <p className="text-xs text-ink-soft">{place.region || coords(place)}</p>

        <div className="mt-4 flex items-end gap-4">
          <p className="tabular text-6xl font-semibold leading-none tracking-tight">
            {pct ?? '–'}
            <span className="text-3xl font-medium text-ink-soft">%</span>
          </p>
          <div className="pb-1">
            <p className="font-medium">{rainWords(pct)}</p>
            <p className="text-sm text-ink-soft">
              {dayLabel(day, { weekday: 'long', day: 'numeric', month: 'short' })}
            </p>
          </div>
        </div>

        {today && (
          <p className="mt-4 text-sm text-ink-soft">
            Expected rain {mm(today.mean_mm)}. Chance means at least {thresholdMm} mm falls in the day.
          </p>
        )}
      </div>
    </div>
  )
}
