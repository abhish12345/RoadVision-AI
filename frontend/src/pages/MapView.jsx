import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { MapContainer, TileLayer, Marker, Popup, CircleMarker, useMap } from 'react-leaflet'
import L from 'leaflet'
import { getMapData, getHeatmapData } from '../api'
import { ArrowLeft, Layers, Map } from 'lucide-react'

// Fix leaflet default icon
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

const CLASS_COLORS = {
  pothole: '#ef4444',
  alligator_crack: '#f97316',
  longitudinal_crack: '#eab308',
  transverse_crack: '#ec4899',
  road_sign: '#22c55e',
  crash_barrier: '#ef4444',
  km_stone: '#06b6d4',
  street_light: '#f59e0b',
  drain: '#8b5cf6',
  default: '#3b82f6',
}

function FitBounds({ markers }) {
  const map = useMap()
  useEffect(() => {
    if (markers.length > 0) {
      const bounds = L.latLngBounds(markers.map(m => [m.lat, m.lon]))
      map.fitBounds(bounds, { padding: [40, 40] })
    }
  }, [markers])
  return null
}

export default function MapView() {
  const { taskId } = useParams()
  const [markers, setMarkers] = useState([])
  const [heatmap, setHeatmap] = useState([])
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState('markers') // markers | heatmap
  const [cameraFilter, setCameraFilter] = useState('')
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    Promise.all([
      getMapData(taskId, cameraFilter || undefined),
      getHeatmapData(taskId)
    ]).then(([mapRes, heatRes]) => {
      setMarkers(mapRes.data.markers)
      setHeatmap(heatRes.data.segments)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [taskId, cameraFilter])

  const center = markers.length > 0
    ? [markers[0].lat, markers[0].lon]
    : [25.23, 87.73] // Farakka default

  return (
    <div className="p-6 space-y-4 h-screen flex flex-col">
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <Link to={`/tasks/${taskId}`} className="flex items-center gap-2 text-gray-400 hover:text-white mb-2 text-sm">
            <ArrowLeft size={14} /> Back to Task
          </Link>
          <h1 className="text-2xl font-bold text-white">Map View</h1>
          <p className="text-gray-500 text-sm">{markers.length} detection markers</p>
        </div>
        <div className="flex items-center gap-3">
          <select className="input w-36" value={cameraFilter} onChange={e => setCameraFilter(e.target.value)}>
            <option value="">All Cameras</option>
            <option value="pave">PAVE</option>
            <option value="row">ROW</option>
          </select>
          <div className="flex bg-gray-800 rounded-lg p-1">
            {[
              { value: 'markers', icon: Map, label: 'Markers' },
              { value: 'heatmap', icon: Layers, label: 'Heatmap' },
            ].map(({ value, icon: Icon, label }) => (
              <button
                key={value}
                onClick={() => setViewMode(value)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition-colors ${
                  viewMode === value ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-2 flex-shrink-0">
        {Object.entries(CLASS_COLORS).filter(([k]) => k !== 'default').map(([cls, color]) => (
          <div key={cls} className="flex items-center gap-1.5 text-xs text-gray-400">
            <div className="w-3 h-3 rounded-full" style={{ background: color }} />
            {cls.replace(/_/g, ' ')}
          </div>
        ))}
      </div>

      {/* Map */}
      <div className="flex-1 rounded-xl overflow-hidden min-h-0">
        {loading ? (
          <div className="w-full h-full bg-gray-800 flex items-center justify-center">
            <p className="text-gray-500">Loading map data...</p>
          </div>
        ) : (
          <MapContainer center={center} zoom={13} style={{ height: '100%', width: '100%' }}>
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; OpenStreetMap contributors'
            />
            <FitBounds markers={markers} />

            {viewMode === 'markers' && markers.map(m => (
              <CircleMarker
                key={m.id}
                center={[m.lat, m.lon]}
                radius={8}
                pathOptions={{
                  color: CLASS_COLORS[m.primary_class] || CLASS_COLORS.default,
                  fillColor: CLASS_COLORS[m.primary_class] || CLASS_COLORS.default,
                  fillOpacity: 0.8,
                  weight: 2,
                }}
                eventHandlers={{ click: () => setSelected(m) }}
              >
                <Popup>
                  <div className="text-sm min-w-48">
                    <div className="font-bold mb-1">{m.primary_class?.replace(/_/g, ' ')}</div>
                    <div className="text-gray-600">Confidence: {m.confidence}%</div>
                    {m.chainage && <div className="text-gray-600">Chainage: {m.chainage?.toFixed(3)} km</div>}
                    <div className="text-gray-600">{m.detection_count} detection(s)</div>
                    <img
                      src={m.annotated_url}
                      alt="Detection"
                      className="mt-2 w-full rounded"
                      onError={e => { e.target.src = m.image_url }}
                    />
                  </div>
                </Popup>
              </CircleMarker>
            ))}

            {viewMode === 'heatmap' && heatmap.map((seg, i) => (
              seg.lat && seg.lon && (
                <CircleMarker
                  key={i}
                  center={[seg.lat, seg.lon]}
                  radius={12}
                  pathOptions={{
                    color: seg.color,
                    fillColor: seg.color,
                    fillOpacity: 0.6,
                    weight: 1,
                  }}
                >
                  <Popup>
                    <div className="text-sm">
                      <div className="font-bold">Ch: {seg.chainage_from} – {seg.chainage_to} km</div>
                      <div>{seg.detection_count} detections</div>
                      <div>Severity: {['Good', 'Fair', 'Poor', 'Very Poor'][seg.severity]}</div>
                    </div>
                  </Popup>
                </CircleMarker>
              )
            ))}
          </MapContainer>
        )}
      </div>
    </div>
  )
}
