import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { dayLabel } from '../lib/rain'

export default function ForecastChart({ days }) {
  const data = days.map((d) => ({
    ...d,
    label: dayLabel(d.date),
    mean_mm: d.mean_mm == null ? null : Number(d.mean_mm.toFixed(1)),
  }))

  return (
    <section aria-labelledby="week-h">
      <h2 id="week-h" className="mb-2 text-base font-semibold">Next 7 days at this spot</h2>
      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart data={data} margin={{ top: 8, right: 0, left: -12, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="#dbe4e8" />
          <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={12} />
          <YAxis yAxisId="p" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tickLine={false} axisLine={false} fontSize={12} />
          <YAxis yAxisId="mm" orientation="right" tickFormatter={(v) => `${v}`} tickLine={false} axisLine={false} fontSize={12} width={28} />
          <Tooltip
            formatter={(v, name) => (name === 'Chance of rain' ? [`${v}%`, name] : [`${v} mm`, name])}
            labelFormatter={(_, p) => (p?.[0] ? dayLabel(p[0].payload.date, { weekday: 'long', day: 'numeric', month: 'short' }) : '')}
          />
          <Bar yAxisId="p" dataKey="chance_pct" name="Chance of rain" fill="#4a7fc1" radius={[3, 3, 0, 0]} />
          <Line yAxisId="mm" dataKey="mean_mm" name="Expected rain" stroke="#17233b" strokeWidth={2} dot={{ r: 3 }} />
        </ComposedChart>
      </ResponsiveContainer>
      <p className="mt-1 text-xs text-ink-soft">Bars: chance of rain. Line: expected rain in mm (right axis).</p>
    </section>
  )
}
