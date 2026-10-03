import { barColor, mm } from '../lib/rain'

const RADII = [10, 25, 50]
const DIRECTION = { N: 'north', NE: 'north-east', E: 'east', SE: 'south-east', S: 'south', SW: 'south-west', W: 'west', NW: 'north-west' }

export default function NearbyList({ data, error, radius, onRadius, onPickCell }) {
  const cells = data?.cells ?? []
  const others = cells.slice(1)
  const wettest = others.reduce((m, c) => (c.chance_pct > (m?.chance_pct ?? -1) ? c : m), null)

  return (
    <section aria-labelledby="nearby-h" className="rounded-2xl bg-white p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 id="nearby-h" className="font-semibold">Around this spot</h2>
        <div className="flex rounded-full bg-mist p-0.5" role="group" aria-label="Search radius">
          {RADII.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => onRadius(r)}
              aria-pressed={r === radius}
              className={`rounded-full px-2.5 py-1 text-xs font-medium ${r === radius ? 'bg-white shadow-sm' : 'text-ink-soft'}`}
            >
              {r} km
            </button>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-ink-soft">{error}</p>}
      {!data && !error && <p className="text-sm text-ink-soft">Loading nearby areas…</p>}
      {data && others.length === 0 && (
        <p className="text-sm text-ink-soft">No other forecast squares within {radius} km. Try a wider circle.</p>
      )}
      {wettest && (
        <p className="mb-2 text-sm">
          Wettest nearby: <span className="font-semibold">{wettest.chance_pct}%</span>, {wettest.distance_km} km to the{' '}
          {DIRECTION[wettest.direction] ?? wettest.direction}.
        </p>
      )}

      <ul className="divide-y divide-line">
        {others.map((c) => (
          <li key={c.cell_id}>
            <button
              type="button"
              onClick={() => onPickCell(c)}
              className="flex w-full items-center gap-3 py-2 text-left text-sm hover:bg-sky"
            >
              <span className="w-24 shrink-0 text-ink-soft">
                {c.distance_km} km {c.direction}
              </span>
              <span className="h-2 flex-1 overflow-hidden rounded-full bg-mist">
                <span className="block h-full rounded-full" style={{ width: `${Math.max(c.chance_pct, 2)}%`, background: barColor(c.chance_pct) }} />
              </span>
              <span className="tabular w-10 text-right font-medium">{c.chance_pct}%</span>
              <span className="tabular hidden w-24 text-right text-ink-soft sm:block">{mm(c.mean_mm)}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
