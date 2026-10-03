import type { LatLng } from '../types'

type Pct = number | null | undefined

export const BINS = [
  { min: 0, color: '#eef3f5', label: '<10%' },
  { min: 10, color: '#d3e4ee', label: '10-19%' },
  { min: 20, color: '#aecde3', label: '20-29%' },
  { min: 30, color: '#7fb0d6', label: '30-49%' },
  { min: 50, color: '#4a7fc1', label: '50-69%' },
  { min: 70, color: '#2a3f8f', label: '70%+' },
] as const

export function rainColor(pct: Pct): string {
  if (pct == null) return '#cfd9de'
  let color: string = BINS[0].color
  for (const b of BINS) if (pct >= b.min) color = b.color
  return color
}

// Bars and meters sit on white, where the lightest band would vanish.
export const barColor = (pct: Pct): string => (pct != null && pct >= BINS[1].min ? rainColor(pct) : '#cfdde4')

// Text that sits on a rain colour needs to flip to white on the dark end.
export const onRainColor = (pct: Pct): string => (pct != null && pct >= 50 ? '#ffffff' : '#13303b')

export function rainWords(pct: Pct): string {
  if (pct == null) return 'No forecast'
  if (pct < 20) return 'Rain unlikely'
  if (pct < 50) return 'Rain possible'
  if (pct < 70) return 'Rain likely'
  return 'Rain very likely'
}

export function dayLabel(iso: string, opts: Intl.DateTimeFormatOptions = { weekday: 'short' }): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, opts)
}

export function mm(v: number | null | undefined): string {
  if (v == null) return 'n/a'
  const n = Number(v)
  return n < 0.1 ? 'under 0.1 mm' : `${n.toFixed(1)} mm`
}

export function coords({ lat, lng }: LatLng): string {
  return `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lng).toFixed(2)}°${lng >= 0 ? 'E' : 'W'}`
}
