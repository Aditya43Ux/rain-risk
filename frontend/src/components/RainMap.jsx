import { useEffect, useRef } from 'react'
import L from 'leaflet'
import { Circle, CircleMarker, GeoJSON, MapContainer, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import { BINS, mm, rainColor } from '../lib/rain'

function tooltipText(c) {
  return c ? `${c.pct}% chance of rain, ${mm(c.mm)} expected` : 'No forecast'
}

function FitToArea({ geo }) {
  const map = useMap()
  const done = useRef(false)
  useEffect(() => {
    if (!geo || done.current || !geo.features.length) return
    map.fitBounds(L.geoJSON(geo).getBounds(), { padding: [24, 24] })
    done.current = true
  }, [geo, map])
  return null
}

function FlyTo({ target }) {
  const map = useMap()
  useEffect(() => {
    if (!target) return
    if (target.bounds) map.flyToBounds(target.bounds, { padding: [24, 24], duration: 0.8 })
    else map.flyTo([target.lat, target.lng], Math.max(map.getZoom(), 10), { duration: 0.8 })
  }, [target, map])
  return null
}

function ClickToPick({ onPick }) {
  useMapEvents({ click: (e) => onPick({ lat: e.latlng.lat, lng: e.latlng.lng }) })
  return null
}

export default function RainMap({ geo, chances, point, radiusKm, flyTarget, onPick, children }) {
  const layerRef = useRef(null)

  // Recolour the existing squares instead of redrawing them, so playback is smooth.
  useEffect(() => {
    const layer = layerRef.current
    if (!layer || !chances) return
    layer.eachLayer((l) => {
      const c = chances[l.feature.id]
      l.setStyle({ fillColor: rainColor(c?.pct) })
      l.setTooltipContent(tooltipText(c))
    })
  }, [chances, geo])

  return (
    <div className="relative h-full w-full">
      <MapContainer center={[21.75, 73.1]} zoom={9} className="h-full w-full" zoomControl={false} attributionControl>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {geo && (
          <GeoJSON
            ref={layerRef}
            data={geo}
            style={(f) => ({
              className: 'rain-cell',
              fillColor: rainColor(chances?.[f.id]?.pct),
              fillOpacity: 0.7,
              color: '#ffffff',
              weight: 1,
            })}
            onEachFeature={(f, layer) => layer.bindTooltip(tooltipText(chances?.[f.id]), { sticky: true })}
          />
        )}
        {point && (
          <>
            <Circle
              center={[point.lat, point.lng]}
              radius={radiusKm * 1000}
              pathOptions={{ color: '#13303b', weight: 1.5, dashArray: '5 6', fill: false, interactive: false }}
            />
            <CircleMarker
              center={[point.lat, point.lng]}
              radius={8}
              pathOptions={{ color: '#ffffff', weight: 3, fillColor: '#13303b', fillOpacity: 1 }}
            />
          </>
        )}
        <FitToArea geo={geo} />
        <FlyTo target={flyTarget} />
        <ClickToPick onPick={onPick} />
      </MapContainer>

      {children}

      <div className="pointer-events-none absolute bottom-3 left-3 z-[1000] rounded-xl bg-white/95 px-3 py-2 shadow-sm">
        <p className="mb-1 text-xs font-medium">Chance of rain</p>
        <ul className="flex gap-1">
          {BINS.map((b) => (
            <li key={b.min} className="flex flex-col items-center gap-0.5">
              <span className="block h-2.5 w-8 rounded-sm" style={{ background: b.color }} />
              <span className="text-[11px] text-ink-soft">{b.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
