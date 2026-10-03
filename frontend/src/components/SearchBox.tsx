import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { searchPlaces } from '../api'
import type { PlaceResult } from '../types'

interface Props {
  onSelect: (place: PlaceResult) => void
  onLocate: () => void
  locating: boolean
}

export default function SearchBox({ onSelect, onLocate, locating }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<PlaceResult[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [status, setStatus] = useState<string | null>(null)
  const listId = useId()
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const q = query.trim()
    if (q.length < 2) { setResults([]); setStatus(null); return }
    const ctrl = new AbortController()
    const t = setTimeout(() => {
      setStatus('Searching…')
      searchPlaces(q, ctrl.signal)
        .then((r) => { setResults(r); setActive(-1); setStatus(r.length ? null : `No places called "${q}" found in India.`) })
        .catch((e: Error) => { if (e.name !== 'AbortError') setStatus(e.message) })
    }, 300)
    return () => { clearTimeout(t); ctrl.abort() }
  }, [query])

  useEffect(() => {
    const close = (e: PointerEvent) => { if (!boxRef.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [])

  function choose(place: PlaceResult) {
    onSelect(place)
    setQuery(place.name)
    setOpen(false)
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive((i) => Math.min(i + 1, results.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter') {
      const pick = results[active >= 0 ? active : 0]
      if (pick) { e.preventDefault(); choose(pick) }
    } else if (e.key === 'Escape') setOpen(false)
  }

  const showList = open && (results.length > 0 || status !== null)

  return (
    <div ref={boxRef} className="relative w-full">
      <div className="flex items-center gap-2 rounded-2xl bg-white p-1.5 pl-4 shadow-md ring-1 ring-black/5 focus-within:ring-2 focus-within:ring-rain">
        <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4 shrink-0 text-ink-soft" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="9" cy="9" r="6" /><path d="m14 14 4 4" strokeLinecap="round" />
        </svg>
        <input
          type="search"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
          aria-label="Search a town or village"
          placeholder="Search a town or village"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          className="min-w-0 flex-1 bg-transparent py-1.5 text-[15px] outline-none placeholder:text-ink-soft"
        />
        <button
          type="button"
          onClick={onLocate}
          disabled={locating}
          className="flex shrink-0 items-center gap-1.5 rounded-xl bg-ink px-3 py-2 text-sm font-medium text-white hover:bg-ink/90 disabled:opacity-60"
        >
          <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="10" cy="10" r="3" /><path d="M10 1v3M10 16v3M1 10h3M16 10h3" strokeLinecap="round" />
          </svg>
          <span className="hidden sm:inline">{locating ? 'Finding you…' : 'My location'}</span>
          <span className="sm:hidden">{locating ? '…' : 'Me'}</span>
        </button>
      </div>

      {showList && (
        <ul id={listId} role="listbox" className="absolute inset-x-0 top-full z-[1100] mt-2 overflow-hidden rounded-2xl bg-white py-1 shadow-lg ring-1 ring-black/5">
          {status && <li className="px-4 py-2.5 text-sm text-ink-soft">{status}</li>}
          {results.map((r, i) => (
            <li
              key={r.id}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onPointerDown={(e) => { e.preventDefault(); choose(r) }}
              onMouseEnter={() => setActive(i)}
              className={`cursor-pointer px-4 py-2.5 ${i === active ? 'bg-mist' : ''}`}
            >
              <span className="block text-[15px] font-medium">{r.name}</span>
              {r.region && <span className="block text-xs text-ink-soft">{r.region}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
