import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { barColor, dayLabel, mm } from '../lib/rain'

export default function WeekChart({ days, selected, onSelect }) {
  const data = days.map((d) => ({ ...d, label: dayLabel(d.date) }))
  return (
    <section aria-labelledby="week-h" className="rounded-2xl bg-white p-5">
      <h2 id="week-h" className="mb-3 font-semibold">The week here</h2>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 4, right: 0, left: -18, bottom: 0 }} onClick={(e) => e?.activePayload && onSelect(e.activePayload[0].payload.date)}>
          <CartesianGrid vertical={false} stroke="#e9f0f3" />
          <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={12} />
          <YAxis domain={[0, 100]} ticks={[0, 50, 100]} tickFormatter={(v) => `${v}%`} tickLine={false} axisLine={false} fontSize={12} />
          <Tooltip
            cursor={{ fill: '#f4f8fa' }}
            formatter={(v, _n, p) => [`${v}% chance, ${mm(p.payload.mean_mm)}`, 'Rain']}
            labelFormatter={(_, p) => (p?.[0] ? dayLabel(p[0].payload.date, { weekday: 'long', day: 'numeric', month: 'short' }) : '')}
          />
          <Bar dataKey="chance_pct" radius={[6, 6, 0, 0]} cursor="pointer">
            {data.map((d) => (
              <Cell
                key={d.date}
                fill={barColor(d.chance_pct)}
                stroke={d.date === selected ? '#13303b' : 'none'}
                strokeWidth={2}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </section>
  )
}
