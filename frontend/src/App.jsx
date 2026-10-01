import { useCallback, useEffect, useMemo, useState } from 'react'
import L from 'leaflet'
import { getMap, getMeta, getNearby, getPoint } from './api'
import RainMap from './components/RainMap'
import SearchBox from './components/SearchBox'
import Timeline from './components/Timeline'
import SpotCard from './components/SpotCard'
import NearbyList from './components/NearbyList'
import WeekChart from './components/WeekChart'
import { dayLabel } from './lib/rain'

const PLAY_MS = 1300

function centroid(geometry) {
  const ring = geometry.coordinates[0]
  const pts = ring.slice(0, -1)
  const lng = pts.reduce((s, p) => s + p[0], 0) / pts.length
  const lat = pts.reduce((s, p) => s + p[1], 0) / pts.length
  return { lat, lng }
}

export default function App() {
  const [meta, setMeta] = useState(null)
  const [geo, setGeo] = useState(null)
  const [byDay, setByDay] = useState({})
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [place, setPlace] = useState(null)
  const [series, setSeries] = useState(null)
  const [pointError, setPointError] = useState(null)
  const [nearby, setNearby] = useState(null)
  const [radius, setRadius] = useState(25)
  const [flyTarget, setFlyTarget] = useState(null)
  const [locating, setLocating] = useState(false)
  const [notice, setNotice] = useState(null)
  const [error, setError] = useState(null)
  const [searchKey, setSearchKey] = useState(0)

  const days = meta?.dates ?? []
  const day = days[index]

  // Load every day's map up front so playback never waits on the network.
  useEffect(() => {
    getMeta()
      .then(async (m) => {
        if (!m.dates.length) throw new Error('No forecast yet. Run "python -m app.ingest" and "python -m app.predict" in the backend folder.')
        const maps = await Promise.all(m.dates.map((d) => getMap(d)))
        const all = {}
        m.dates.forEach((d, i) => {
          all[d] = Object.fromEntries(
            maps[i].features.map((f) => [f.id, { pct: f.properties.chance_pct, mm: f.properties.mean_mm }]),
          )
        })
        setGeo(maps.find((fc) => fc.features.length) ?? maps[0])
        setByDay(all)
        setMeta(m)
      })
      .catch((e) => setError(e.message))
  }, [])

  const centres = useMemo(
    () => (geo ? Object.fromEntries(geo.features.map((f) => [f.id, centroid(f.geometry)])) : {}),
    [geo],
  )

  // the wettest square in the whole area for each day
  const wettest = useMemo(() => {
    const out = {}
    for (const [d, cells] of Object.entries(byDay)) {
      let best = null
      for (const [id, c] of Object.entries(cells)) if (c.pct != null && (!best || c.pct > best.pct)) best = { id, ...c }
      out[d] = best
    }
    return out
  }, [byDay])

  const pick = useCallback((p, fly = true) => {
    setPlace(p)
    setNearby(null)
    if (fly) setFlyTarget({ lat: p.lat, lng: p.lng })
  }, [])

  useEffect(() => {
    if (!place) return
    let stale = false
    setPointError(null)
    getPoint(place)
      .then((d) => !stale && setSeries(d))
      .catch((e) => {
        if (stale) return
        setSeries(null)
        setPointError(e.status === 404 ? 'This spot is outside the forecast area. Rain chances are only available inside the coloured squares.' : e.message)
      })
    return () => { stale = true }
  }, [place])

  useEffect(() => {
    if (!place || !day || pointError) return
    let stale = false
    getNearby(place, day, radius).then((d) => !stale && setNearby(d)).catch(() => { })
    return () => { stale = true }
  }, [place, day, radius, pointError])

  useEffect(() => {
    if (!playing || days.length < 2) return
    const t = setInterval(() => setIndex((i) => (i + 1) % days.length), PLAY_MS)
    return () => clearInterval(t)
  }, [playing, days.length])

  useEffect(() => {
    if (!notice) return
    const t = setTimeout(() => setNotice(null), 5000)
    return () => clearTimeout(t)
  }, [notice])

  function locate() {
    if (!navigator.geolocation) { setNotice('Your browser does not share location. Search for your town instead.'); return }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => { setLocating(false); pick({ lat: pos.coords.latitude, lng: pos.coords.longitude, name: 'Your location' }) },
      (err) => {
        setLocating(false)
        setNotice(err.code === 1 ? 'Location access was blocked. Allow it in your browser, or search for your town.' : 'Could not find your location. Search for your town instead.')
      },
      { timeout: 10000, maximumAge: 300000 },
    )
  }

  function showArea() {
    if (geo) setFlyTarget({ bounds: L.geoJSON(geo).getBounds() })
  }

  function selectDay(i) {
    setPlaying(false)
    setIndex(i)
  }

  const spotByDate = useMemo(
    () => (series ? Object.fromEntries(series.days.map((d) => [d.date, d])) : {}),
    [series],
  )
  const today = spotByDate[day]
  const best = wettest[day]

  return (
    <div className="flex h-dvh flex-col lg:flex-row">
      <div className="relative h-[46dvh] shrink-0 lg:h-full lg:flex-1">
        <RainMap
          geo={geo}
          chances={byDay[day]}
          point={place}
          radiusKm={radius}
          flyTarget={flyTarget}
          onPick={(p) => pick(p, false)}
        >
          <div className="absolute inset-x-3 top-3 z-[1100] lg:left-4 lg:right-auto lg:w-[26rem]">
            <SearchBox onSelect={(p) => pick(p)} onLocate={locate} locating={locating} />
            {notice && (
              <p role="status" className="mt-2 rounded-xl bg-ink px-4 py-2.5 text-sm text-white shadow-md">{notice}</p>
            )}
          </div>
        </RainMap>
      </div>

      <aside className="flex-1 overflow-y-auto lg:w-[27rem] lg:flex-none">
        <div className="sticky top-0 z-10 bg-sky/95 px-4 pb-3 pt-4 backdrop-blur">
          <div className="mb-3 flex items-baseline justify-between gap-3">
            <h1 className="text-xl font-semibold">Rain outlook</h1>
            {meta?.updated_at && (
              <p className="text-xs text-ink-soft">
                Updated {new Date(meta.updated_at).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })}
              </p>
            )}
          </div>
          {days.length > 0 && (
            <Timeline
              days={days}
              index={index}
              onIndex={selectDay}
              playing={playing}
              onTogglePlay={() => setPlaying((p) => !p)}
              valueFor={(d) => (series ? spotByDate[d]?.chance_pct : wettest[d]?.pct)}
              caption={series ? 'Chance of rain at this spot' : 'Highest chance anywhere in the area'}
            />
          )}
        </div>

        <div className="space-y-3 px-4 pb-6">
          {error && <p role="alert" className="rounded-2xl bg-red-50 p-4 text-sm text-red-800">{error}</p>}
          {!error && !meta && <p className="text-sm text-ink-soft">Loading the forecast…</p>}

          {meta && !place && (
            <div className="rounded-2xl bg-white p-5">
              <p className="font-semibold">Where do you want to check?</p>
              <p className="mt-1 text-sm text-ink-soft">
                Search for a town or village, use your location, or tap anywhere on the map.
              </p>
              {best && day && (
                <button
                  type="button"
                  onClick={() => pick({ ...centres[best.id], name: 'Wettest spot in the area' })}
                  className="mt-4 w-full rounded-xl bg-mist px-4 py-3 text-left hover:bg-line"
                >
                  <span className="block text-sm text-ink-soft">Wettest spot on {dayLabel(day, { weekday: 'long' })}</span>
                  <span className="block font-semibold">{best.pct}% chance of rain. Show me</span>
                </button>
              )}
            </div>
          )}

          {place && (
            <>
              <SpotCard place={place} day={day} today={today} error={pointError} onShowArea={showArea} />
              {!pointError && (
                <>
                  <NearbyList
                    data={nearby}
                    radius={radius}
                    onRadius={setRadius}
                    onPickCell={(c) => pick({ lat: c.lat, lng: c.lon, name: `${c.distance_km} km ${c.direction} of your spot` })}
                  />
                  {series && <WeekChart days={series.days} selected={day} onSelect={(d) => selectDay(days.indexOf(d))} />}
                </>
              )}
            </>
          )}

          <p className="px-1 pt-2 text-xs leading-relaxed text-ink-soft">
            Chances come from a machine-learning model trained on three monsoons of ECMWF forecasts and NASA satellite rainfall.
            It was tuned for June to September, so treat other months with care. Days run from 5:30 am to 5:30 am Indian time.
          </p>
        </div>
      </aside>
    </div>
  )
}
