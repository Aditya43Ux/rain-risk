async function get(path, params = {}) {
  const qs = new URLSearchParams(params).toString()
  const res = await fetch(`/api${path}${qs ? `?${qs}` : ''}`)
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* keep statusText */ }
    throw new Error(detail)
  }
  return res.json()
}

export const getMeta = () => get('/meta')
export const getMap = (day) => get('/forecast/map', { day })
export const getPoint = ({ lat, lng }) => get('/forecast/point', { lat, lon: lng })
export const getNearby = ({ lat, lng }, day, radiusKm) =>
  get('/forecast/nearby', { lat, lon: lng, day, radius_km: radiusKm })
