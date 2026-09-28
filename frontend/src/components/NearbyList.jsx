import { rainColor, mm } from '../lib/rain'

const RADII = [10, 25, 50]

export default function NearbyList({ data, radius, onRadius }) {
  const cells = data?.cells ?? []
  const wettest = cells.reduce((m, c) => (c.chance_pct > (m?.chance_pct ?? -1) ? c : m), null)

  return (
    <section aria-labelledby="nearby-h">
      <div className="mb-2 flex items-center justify-between">
        <h2 id="nearby-h" className="text-base font-semibold">Nearby areas</h2>
        <div className="flex gap-1" role="group" aria-label="Search radius">
          {RADII.map((r) => (
            <button
              key={r}
              onClick={() => onRadius(r)}
              aria-pressed={r === radius}
              className={`rounded px-2 py-0.5 text-xs ${
                r === radius ? 'bg-ink text-white' : 'bg-mist hover:bg-line'
              }`}
            >
              {r} km
            </button>
          ))}
        </div>
      </div>

      {!data && <p className="text-sm text-ink-soft">Loading…</p>}
      {data && cells.length === 0 && (
        <p className="text-sm text-ink-soft">No forecast cells within {radius} km. Try a larger radius.</p>
      )}
      {wettest && cells.length > 1 && (
        <p className="mb-2 text-sm text-ink-soft">
          Highest chance nearby: {wettest.chance_pct}%,{' '}
          {wettest.distance_km < 1 ? 'right here' : `${wettest.distance_km} km ${wettest.direction ?? ''}`}.
        </p>
      )}

      <ul className="divide-y divide-line">
        {cells.map((c, i) => (
          <li key={c.cell_id} className="flex items-center gap-3 py-2 text-sm">
            <span className="w-20 shrink-0 text-ink-soft">
              {i === 0 ? 'This cell' : `${c.distance_km} km ${c.direction ?? ''}`}
            </span>
            <span className="h-2 flex-1 overflow-hidden rounded-full bg-mist">
              <span
                className="block h-full rounded-full"
                style={{ width: `${c.chance_pct}%`, background: rainColor(c.chance_pct) }}
              />
            </span>
            <span className="w-10 text-right font-medium">{c.chance_pct}%</span>
            <span className="hidden w-16 text-right text-ink-soft sm:block">{mm(c.mean_mm)}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
