// Shapes of the backend API (backend/app/main.py) and the app's own models.
import type { Feature, FeatureCollection, Polygon } from 'geojson'
import type { LatLngBounds } from 'leaflet'

export interface LatLng {
  lat: number
  lng: number
}

/** A spot the user picked: from search, their location, or the map. */
export interface Place extends LatLng {
  name?: string
  region?: string
}

export interface PlaceResult extends Place {
  id: number
  name: string
  region: string
}

export interface CellProperties {
  /** One entry per AreaResponse.dates; null where the cell has no forecast. */
  chance_pct: (number | null)[]
  mean_mm: (number | null)[]
}

export type CellFeature = Feature<Polygon, CellProperties> & { id: number }
export type Grid = FeatureCollection<Polygon, CellProperties> & { features: CellFeature[] }

export interface AreaMeta {
  model: string
  rain_threshold_mm: number
  updated_at: string | null
  dates: string[]
}

export interface AreaResponse extends AreaMeta {
  grid: Grid
}

export interface SpotDay {
  date: string
  chance_pct: number | null
  mean_mm: number | null
  p90_mm: number | null
}

export interface PointResponse {
  cell: { id: number; lat: number; lon: number }
  days: SpotDay[]
}

export type Compass = 'N' | 'NE' | 'E' | 'SE' | 'S' | 'SW' | 'W' | 'NW'

export interface NearbyCell {
  cell_id: number
  lat: number
  lon: number
  distance_km: number
  direction: Compass | null
  chance_pct: number | null
  mean_mm: number | null
}

export interface NearbyResponse {
  day: string
  radius_km: number
  cells: NearbyCell[]
}

/** One cell on one day, as the map and timeline use it. */
export interface Chance {
  pct: number | null
  mm: number | null
}

/** cell id -> chance, for one day */
export type DayChances = Record<number, Chance>

export type FlyTarget = LatLng | { bounds: LatLngBounds }
