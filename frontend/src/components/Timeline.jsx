import { dayLabel, onRainColor, rainColor } from '../lib/rain'

export default function Timeline({ days, index, onIndex, playing, onTogglePlay, valueFor, caption }) {
  return (
    <section aria-label="Forecast days">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm text-ink-soft">{caption}</p>
        <button
          type="button"
          onClick={onTogglePlay}
          aria-pressed={playing}
          className="flex items-center gap-1.5 rounded-full bg-mist px-3 py-1.5 text-sm font-medium hover:bg-line"
        >
          {playing ? (
            <svg aria-hidden="true" viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="currentColor"><rect x="3" y="2" width="3.5" height="12" rx="1" /><rect x="9.5" y="2" width="3.5" height="12" rx="1" /></svg>
          ) : (
            <svg aria-hidden="true" viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="currentColor"><path d="M4 2.5v11a.5.5 0 0 0 .77.42l8.5-5.5a.5.5 0 0 0 0-.84l-8.5-5.5A.5.5 0 0 0 4 2.5Z" /></svg>
          )}
          {playing ? 'Pause' : 'Play week'}
        </button>
      </div>

      <div role="tablist" className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))` }}>
        {days.map((d, i) => {
          const pct = valueFor(d)
          const active = i === index
          return (
            <button
              key={d}
              role="tab"
              aria-selected={active}
              aria-label={`${dayLabel(d, { weekday: 'long', day: 'numeric', month: 'long' })}${pct != null ? `, ${pct}% chance of rain` : ''}`}
              onClick={() => onIndex(i)}
              className={`flex flex-col items-center rounded-xl px-0.5 pb-1.5 pt-2 transition-colors ${active ? 'bg-ink text-white' : 'bg-white hover:bg-mist'}`}
            >
              <span className="text-[11px] leading-none">{dayLabel(d)}</span>
              <span className="mt-0.5 text-base font-semibold leading-tight">{dayLabel(d, { day: 'numeric' })}</span>
              <span
                className="tabular mt-1 w-full max-w-10 rounded-md py-0.5 text-[11px] font-medium"
                style={{ background: rainColor(pct), color: onRainColor(pct) }}
              >
                {pct == null ? '–' : `${pct}%`}
              </span>
            </button>
          )
        })}
      </div>

      <input
        type="range"
        min={0}
        max={days.length - 1}
        value={index}
        onChange={(e) => onIndex(Number(e.target.value))}
        aria-label="Scrub through the week"
        className="mt-3 w-full accent-[#13303b]"
      />
    </section>
  )
}
