import { useEffect, useRef } from 'react'
import L from 'leaflet'
import { MapContainer, TileLayer, GeoJSON, Circle, CircleMarker, useMap, useMapEvents } from 'react-leaflet'
import { BINS, rainColor, mm } from '../lib/rain'

function FitToData({ data }) {
  const map = useMap()
  const done = useRef(false)
  useEffect(() => {
    if (!data || done.current || !data.features.length) return
    map.fitBounds(L.geoJSON(data).getBounds(), { padding: [24, 24] })
    done.current = true
  }, [data, map])
  return null
}

function ClickToPick({ onPick }) {
  useMapEvents({ click: (e) => onPick(e.latlng) })
  return null
}

export default function RainMap({ cells, day, point, radiusKm, onPick }) {
  return (
    <div className="relative h-full w-full">
      <MapContainer center={[20.5, 78.9]} zoom={5} className="h-full w-full" zoomControl>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {cells && (
          <GeoJSON
            key={day}
            data={cells}
            style={(f) => ({
              fillColor: rainColor(f.properties.chance_pct),
              fillOpacity: 0.62,
              color: '#ffffff',
              weight: 1,
            })}
            onEachFeature={(f, layer) =>
              layer.bindTooltip(
                `${f.properties.chance_pct}% chance, ${mm(f.properties.mean_mm)} expected`,
                { sticky: true },
              )
            }
          />
        )}
        {point && (
          <>
            <Circle
              center={[point.lat, point.lng]}
              radius={radiusKm * 1000}
              pathOptions={{ color: '#17233b', weight: 1.5, dashArray: '6 6', fill: false }}
            />
            <CircleMarker
              center={[point.lat, point.lng]}
              radius={6}
              pathOptions={{ color: '#fff', weight: 2, fillColor: '#17233b', fillOpacity: 1 }}
            />
          </>
        )}
        <FitToData data={cells} />
        <ClickToPick onPick={onPick} />
      </MapContainer>

      <div className="absolute bottom-4 left-4 z-[1000] rounded-md bg-white/95 px-3 py-2 text-xs shadow">
        <p className="mb-1.5 font-medium">Chance of rain</p>
        <ul className="flex gap-2">
          {BINS.map((b) => (
            <li key={b.min} className="flex flex-col items-center gap-1">
              <span className="block h-3 w-9 rounded-sm" style={{ background: b.color }} />
              <span className="text-ink-soft">{b.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
