// One sequential ramp, pale mist to deep indigo. Keep the map and the bars on the same scale.
export const BINS = [
  { min: 0, color: '#e6eef1', label: '0-19%' },
  { min: 20, color: '#b7d3e3', label: '20-39%' },
  { min: 40, color: '#7fb0d6', label: '40-59%' },
  { min: 60, color: '#4a7fc1', label: '60-79%' },
  { min: 80, color: '#2a3f8f', label: '80-100%' },
]

export function rainColor(pct) {
  if (pct == null) return '#cbd5db'
  let color = BINS[0].color
  for (const b of BINS) if (pct >= b.min) color = b.color
  return color
}

export function dayLabel(iso, opts = { weekday: 'short' }) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, opts)
}

export function mm(v) {
  return v == null ? 'n/a' : `${Number(v).toFixed(1)} mm`
}
