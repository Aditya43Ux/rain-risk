async function get(path, params = {}) {
  const qs = new URLSearchParams(params).toString()
  const res = await fetch(`/api${path}${qs ? `?${qs}` : ''}`)
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* keep statusText */ }
    const err = new Error(detail)
    err.status = res.status
    throw err
  }
  return res.json()
}

export const getArea = () => get('/forecast/area')
export const getPoint = ({ lat, lng }) => get('/forecast/point', { lat, lon: lng })
export const getNearby = ({ lat, lng }, day, radiusKm) =>
  get('/forecast/nearby', { lat, lon: lng, day, radius_km: radiusKm })

// Place search, straight from the browser (free, no key). Limited to India.
export async function searchPlaces(query, signal) {
  const params = new URLSearchParams({ name: query, count: '6', language: 'en', format: 'json', countryCode: 'IN' })
  const res = await fetch(`https://geocoding-api.open-meteo.com/v1/search?${params}`, { signal })
  if (!res.ok) throw new Error('Place search is unavailable right now.')
  const data = await res.json()
  return (data.results ?? []).map((r) => ({
    id: r.id,
    name: r.name,
    region: [r.admin2, r.admin1].filter(Boolean).filter((v, i, a) => a.indexOf(v) === i).join(', '),
    lat: r.latitude,
    lng: r.longitude,
  }))
}
