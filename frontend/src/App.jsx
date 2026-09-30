import { useEffect, useMemo, useState } from 'react'
import { getMap, getMeta, getNearby, getPoint } from './api'
import RainMap from './components/RainMap'
import DayStrip from './components/DayStrip'
import NearbyList from './components/NearbyList'
import ForecastChart from './components/ForecastChart'
import { dayLabel } from './lib/rain'

export default function App() {
  const [meta, setMeta] = useState(null)
  const [day, setDay] = useState(null)
  const [cells, setCells] = useState(null)
  const [point, setPoint] = useState(null)
  const [radius, setRadius] = useState(25)
  const [nearby, setNearby] = useState(null)
  const [series, setSeries] = useState(null)
  const [error, setError] = useState(null)
  const [pointError, setPointError] = useState(null)

  useEffect(() => {
    getMeta()
      .then((m) => {
        if (!m.dates.length) throw new Error('No forecast data yet. Run "python -m app.ingest" in the backend folder.')
        setMeta(m)
        setDay(m.dates[0])
      })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!day) return
    let stale = false
    getMap(day).then((d) => !stale && setCells(d)).catch((e) => !stale && setError(e.message))
    return () => { stale = true }
  }, [day])

  useEffect(() => {
    if (!point) return
    let stale = false
    setPointError(null)
    getPoint(point)
      .then((d) => !stale && setSeries(d))
      .catch((e) => { if (!stale) { setSeries(null); setNearby(null); setPointError(e.message) } })
    return () => { stale = true }
  }, [point])

  useEffect(() => {
    if (!point || !day || pointError) return
    let stale = false
    getNearby(point, day, radius).then((d) => !stale && setNearby(d)).catch(() => { })
    return () => { stale = true }
  }, [point, day, radius, pointError])

  const chanceByDate = useMemo(
    () => (series ? Object.fromEntries(series.days.map((d) => [d.date, d.chance_pct])) : null),
    [series],
  )
  const here = series?.days.find((d) => d.date === day)

  return (
    <div className="flex h-dvh flex-col lg:flex-row">
      <main className="h-[45dvh] min-h-64 lg:h-full lg:flex-1">
        <RainMap cells={cells} day={day} point={point} radiusKm={radius} onPick={(ll) => { setNearby(null); setPoint(ll) }} />
      </main>

      <aside className="flex-1 overflow-y-auto border-line p-5 lg:w-[26rem] lg:flex-none lg:border-l">
        <h1 className="text-xl font-semibold">Rain outlook</h1>
        {meta && (
          <p className="mt-1 text-sm text-ink-soft">
            Chance of at least {meta.rain_threshold_mm} mm of rain in a day. Model: {meta.model}. Updated{' '}
            {new Date(meta.updated_at).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })}.
          </p>
        )}

        {error && <p role="alert" className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</p>}

        {meta && day && (
          <div className="mt-4">
            <DayStrip dates={meta.dates} day={day} onSelect={setDay} chanceByDate={chanceByDate} />
          </div>
        )}

        {!point && meta && (
          <p className="mt-6 text-sm text-ink-soft">
            Click anywhere on the map to see the chance of rain there and in the areas around it.
          </p>
        )}

        {pointError && <p role="alert" className="mt-6 text-sm text-red-800">{pointError} Pick a spot inside the coloured area.</p>}

        {here && (
          <p className="mt-6 text-lg">
            <span className="font-semibold">{here.chance_pct}% chance of rain</span> here on{' '}
            {dayLabel(day, { weekday: 'long' })}, with about {here.mean_mm?.toFixed(1) ?? '0'} mm expected.
          </p>
        )}

        {point && !pointError && (
          <div className="mt-6 space-y-8">
            <NearbyList data={nearby} radius={radius} onRadius={setRadius} />
            {series && <ForecastChart days={series.days} />}
          </div>
        )}

        <p className="mt-8 text-xs text-ink-soft">
          Probabilities come from a machine-learning model trained on three monsoons of ECMWF forecasts and NASA satellite rainfall. It was tuned for June to September, so treat other months with care.
        </p>
      </aside>
    </div>
  )
}
