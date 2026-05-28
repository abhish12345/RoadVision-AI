import { useEffect, useState } from 'react'
import { getModelStatus } from '../api'
import { Brain, CheckCircle, XCircle, ChevronDown, ChevronUp } from 'lucide-react'

const MODEL_LABELS = {
  // PAVE — all run in parallel
  rdd2022_yolov8m:          { label: 'RDD2022 YOLOv8m (D00/D10/D20/D40)', camera: 'PAVE', role: 'Parallel' },
  crack_seg_yolov8m:        { label: 'Crack Seg YOLOv8m',                  camera: 'PAVE', role: 'Parallel' },
  pothole_seg_yolov8m:      { label: 'Pothole Seg YOLOv8m',                camera: 'PAVE', role: 'Parallel' },
  pothole_finetune:         { label: 'Pothole Fine-tuned',                  camera: 'PAVE', role: 'Parallel' },
  pothole_seg_yolov8n:      { label: 'Pothole Seg YOLOv8n (fast)',          camera: 'PAVE', role: 'Backup' },
  road_damage:              { label: 'Road Damage Fallback',                camera: 'PAVE', role: 'Fallback' },
  // ROW — all run in parallel
  row_road_objects_yolov8s: { label: 'Road Objects YOLOv8s (10 classes)',   camera: 'ROW',  role: 'Parallel' },
  yolov8m_coco:             { label: 'YOLOv8m COCO (80 classes)',           camera: 'ROW',  role: 'Parallel' },
  // Base
  yolov8s_coco:             { label: 'YOLOv8s COCO',                        camera: 'BASE', role: 'Base' },
  yolov8n_coco:             { label: 'YOLOv8n COCO',                        camera: 'BASE', role: 'Base' },
}

const ROLE_COLORS = {
  'Parallel': 'bg-green-900/40 text-green-400 border-green-800',
  'Backup':   'bg-yellow-900/40 text-yellow-400 border-yellow-800',
  'Fallback': 'bg-gray-800 text-gray-500 border-gray-700',
  'Base':     'bg-gray-800 text-gray-600 border-gray-700',
}

const CAMERA_COLORS = {
  'PAVE': 'bg-orange-900/40 text-orange-400',
  'ROW':  'bg-green-900/40 text-green-400',
  'BASE': 'bg-gray-800 text-gray-500',
}

export default function ModelStatus() {
  const [status, setStatus] = useState(null)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    getModelStatus().then(r => setStatus(r.data)).catch(() => {})
  }, [])

  if (!status) return null

  const { models, summary } = status

  // Count parallel models per camera
  const paveParallel = Object.entries(models).filter(([k, v]) =>
    MODEL_LABELS[k]?.camera === 'PAVE' &&
    MODEL_LABELS[k]?.role === 'Parallel' &&
    v.available
  ).length

  const rowParallel = Object.entries(models).filter(([k, v]) =>
    MODEL_LABELS[k]?.camera === 'ROW' &&
    MODEL_LABELS[k]?.role === 'Parallel' &&
    v.available
  ).length

  return (
    <div className="card">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between"
      >
        <div className="flex items-center gap-2">
          <Brain size={16} className="text-purple-400" />
          <span className="font-semibold text-white text-sm">AI Models</span>
          <span className="text-xs text-gray-500">
            {summary.total_available}/{summary.total_models} loaded
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-green-400">
            PAVE: {paveParallel} parallel · ROW: {rowParallel} parallel
          </span>
          {expanded
            ? <ChevronUp size={14} className="text-gray-500" />
            : <ChevronDown size={14} className="text-gray-500" />}
        </div>
      </button>

      {expanded && (
        <div className="mt-4 space-y-2">

          {/* Pipeline summary */}
          <div className="grid grid-cols-2 gap-2 mb-3">
            <div className="bg-orange-900/10 border border-orange-900/40 rounded-lg p-3">
              <div className="text-xs text-orange-400 font-medium mb-1">🛣️ PAVE Pipeline</div>
              <div className="text-xs text-gray-300">{paveParallel} models run in parallel</div>
              <div className="text-xs text-gray-500 mt-1">→ NMS merge → FP filter</div>
              <div className="text-xs text-green-400 mt-1">Detects: cracks + potholes</div>
            </div>
            <div className="bg-green-900/10 border border-green-900/40 rounded-lg p-3">
              <div className="text-xs text-green-400 font-medium mb-1">🚧 ROW Pipeline</div>
              <div className="text-xs text-gray-300">{rowParallel} models run in parallel</div>
              <div className="text-xs text-gray-500 mt-1">→ NMS merge → skip irrelevant</div>
              <div className="text-xs text-green-400 mt-1">Detects: signs + assets</div>
            </div>
          </div>

          {/* All models list */}
          <div className="text-xs text-gray-600 font-medium uppercase tracking-wide mb-1">
            All Models
          </div>
          {Object.entries(models).map(([key, info]) => {
            const meta = MODEL_LABELS[key] || { label: key, camera: '?', role: '—' }
            const roleColor = ROLE_COLORS[meta.role] || ROLE_COLORS['Base']
            const camColor = CAMERA_COLORS[meta.camera] || CAMERA_COLORS['BASE']

            return (
              <div
                key={key}
                className={`flex items-center justify-between py-1.5 px-2 rounded-lg ${
                  info.available ? 'hover:bg-gray-800' : 'opacity-40'
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  {info.available
                    ? <CheckCircle size={12} className="text-green-400 flex-shrink-0" />
                    : <XCircle size={12} className="text-red-400 flex-shrink-0" />}
                  <span className={`text-xs truncate ${info.available ? 'text-gray-300' : 'text-gray-600'}`}>
                    {meta.label}
                  </span>
                </div>
                <div className="flex items-center gap-2 ml-2 flex-shrink-0">
                  <span className={`text-xs px-1.5 py-0.5 rounded border ${roleColor}`}>
                    {meta.role}
                  </span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${camColor}`}>
                    {meta.camera}
                  </span>
                  <span className="text-xs text-gray-600 w-12 text-right">
                    {info.available ? `${info.size_mb}MB` : '—'}
                  </span>
                </div>
              </div>
            )
          })}

          <div className="mt-2 pt-2 border-t border-gray-800 text-xs text-gray-600">
            All models run automatically. No manual selection needed.
          </div>
        </div>
      )}
    </div>
  )
}
