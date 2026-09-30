// One sequential ramp, pale mist to deep indigo. Keep the map and the bars on the same scale.
export const BINS = [
  { min: 0, color: '#eef3f5', label: '<10%' },
  { min: 10, color: '#d3e4ee', label: '10-19%' },
  { min: 20, color: '#aecde3', label: '20-29%' },
  { min: 30, color: '#7fb0d6', label: '30-49%' },
  { min: 50, color: '#4a7fc1', label: '50-69%' },
  { min: 70, color: '#2a3f8f', label: '70%+' },
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
