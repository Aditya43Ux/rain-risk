import type { AreaResponse, LatLng, NearbyResponse, PlaceResult, PointResponse } from './types'

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message)
  }
}

async function get<T>(path: string, params: Record<string, string | number> = {}): Promise<T> {
  const qs = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString()
  const res = await fetch(`/api${path}${qs ? `?${qs}` : ''}`)
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* keep statusText */ }
    throw new ApiError(detail, res.status)
  }
  return res.json() as Promise<T>
}

export const getArea = () => get<AreaResponse>('/forecast/area')
export const getPoint = ({ lat, lng }: LatLng) => get<PointResponse>('/forecast/point', { lat, lon: lng })
export const getNearby = ({ lat, lng }: LatLng, day: string, radiusKm: number) =>
  get<NearbyResponse>('/forecast/nearby', { lat, lon: lng, day, radius_km: radiusKm })

interface GeocodingResult {
  id: number
  name: string
  latitude: number
  longitude: number
  admin1?: string
  admin2?: string
}

// Place search, straight from the browser (free, no key). Limited to India.
export async function searchPlaces(query: string, signal?: AbortSignal): Promise<PlaceResult[]> {
  const params = new URLSearchParams({ name: query, count: '6', language: 'en', format: 'json', countryCode: 'IN' })
  const res = await fetch(`https://geocoding-api.open-meteo.com/v1/search?${params}`, { signal })
  if (!res.ok) throw new Error('Place search is unavailable right now.')
  const data: { results?: GeocodingResult[] } = await res.json()
  return (data.results ?? []).map((r) => ({
    id: r.id,
    name: r.name,
    region: [r.admin2, r.admin1].filter((v): v is string => Boolean(v)).filter((v, i, a) => a.indexOf(v) === i).join(', '),
    lat: r.latitude,
    lng: r.longitude,
  }))
}
