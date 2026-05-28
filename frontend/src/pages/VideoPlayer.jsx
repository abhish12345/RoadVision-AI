import { useEffect, useRef, useState } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import { getTask, getVideoDetections } from '../api'
import { ArrowLeft, Play, Pause, SkipBack, SkipForward, Maximize2 } from 'lucide-react'

const CLASS_COLORS = {
  pothole: '#ef4444',
  alligator_crack: '#f97316',
  longitudinal_crack: '#eab308',
  transverse_crack: '#ec4899',
  patching: '#94a3b8',
  bleeding_ravelling: '#3b82f6',
  road_sign: '#22c55e',
  crash_barrier: '#ef4444',
  km_stone: '#06b6d4',
  street_light: '#f59e0b',
  drain: '#8b5cf6',
  default: '#3b82f6',
}

export default function VideoPlayer() {
  const { taskId } = useParams()
  const [searchParams] = useSearchParams()
  const videoId = searchParams.get('videoId')

  const [task, setTask] = useState(null)
  const [detections, setDetections] = useState([])
  const [currentDetection, setCurrentDetection] = useState(null)
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [loading, setLoading] = useState(true)

  const canvasRef = useRef(null)
  const imgRef = useRef(null)
  const intervalRef = useRef(null)
  const detectionIndexRef = useRef(0)

  useEffect(() => {
    Promise.all([
      getTask(taskId),
      videoId ? getVideoDetections(videoId, { limit: 500 }) : Promise.resolve({ data: { detections: [] } })
    ]).then(([taskRes, detRes]) => {
      setTask(taskRes.data)
      const dets = detRes.data.detections.filter(d => d.detections?.length > 0)
      setDetections(dets)
      if (dets.length > 0) {
        setCurrentDetection(dets[0])
        setDuration(dets[dets.length - 1]?.timestamp_sec || 0)
      }
      setLoading(false)
    })
  }, [taskId, videoId])

  // Draw bounding boxes on canvas
  const drawBoxes = (img, dets) => {
    const canvas = canvasRef.current
    if (!canvas || !img) return
    const ctx = canvas.getContext('2d')
    canvas.width = img.naturalWidth || img.width
    canvas.height = img.naturalHeight || img.height
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    dets.forEach(det => {
      const color = CLASS_COLORS[det.normalized_class] || CLASS_COLORS.default
      const { x1, y1, x2, y2 } = det
      ctx.strokeStyle = color
      ctx.lineWidth = 3
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)

      // Label background
      const label = `${det.normalized_class?.replace(/_/g, ' ')} ${(det.confidence * 100).toFixed(0)}%`
      ctx.font = 'bold 14px sans-serif'
      const tw = ctx.measureText(label).width
      ctx.fillStyle = color
      ctx.fillRect(x1, y1 - 22, tw + 8, 22)
      ctx.fillStyle = '#fff'
      ctx.fillText(label, x1 + 4, y1 - 6)
    })
  }

  // Auto-play through detections
  useEffect(() => {
    if (playing && detections.length > 0) {
      intervalRef.current = setInterval(() => {
        detectionIndexRef.current = (detectionIndexRef.current + 1) % detections.length
        const det = detections[detectionIndexRef.current]
        setCurrentDetection(det)
        setCurrentTime(det.timestamp_sec || 0)
      }, 500) // advance every 500ms
    } else {
      clearInterval(intervalRef.current)
    }
    return () => clearInterval(intervalRef.current)
  }, [playing, detections])

  const goTo = (idx) => {
    const clamped = Math.max(0, Math.min(detections.length - 1, idx))
    detectionIndexRef.current = clamped
    setCurrentDetection(detections[clamped])
    setCurrentTime(detections[clamped]?.timestamp_sec || 0)
  }

  const handleImgLoad = () => {
    if (currentDetection) drawBoxes(imgRef.current, currentDetection.detections || [])
  }

  useEffect(() => {
    if (currentDetection && imgRef.current?.complete) {
      drawBoxes(imgRef.current, currentDetection.detections || [])
    }
  }, [currentDetection])

  const formatTime = (s) => {
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  if (loading) return <div className="p-6 text-gray-500">Loading...</div>

  return (
    <div className="p-6 space-y-4">
      <div>
        <Link to={`/tasks/${taskId}`} className="flex items-center gap-2 text-gray-400 hover:text-white mb-2 text-sm">
          <ArrowLeft size={14} /> Back to Task
        </Link>
        <h1 className="text-2xl font-bold text-white">Video Replay with AI Annotations</h1>
        <p className="text-gray-500 text-sm">{detections.length} annotated frames</p>
      </div>

      {detections.length === 0 ? (
        <div className="card text-center py-16">
          <p className="text-gray-500">No detections found for this video. Process a video first.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main viewer */}
          <div className="lg:col-span-2 space-y-3">
            <div className="relative bg-black rounded-xl overflow-hidden aspect-video">
              {currentDetection && (
                <>
                  <img
                    ref={imgRef}
                    src={`http://localhost:8000/api/images/serve/${currentDetection.id}`}
                    alt="Frame"
                    className="w-full h-full object-contain"
                    onLoad={handleImgLoad}
                    crossOrigin="anonymous"
                  />
                  <canvas
                    ref={canvasRef}
                    className="absolute inset-0 w-full h-full"
                    style={{ pointerEvents: 'none' }}
                  />
                </>
              )}
              {/* Overlay info */}
              {currentDetection && (
                <div className="absolute top-3 left-3 bg-black/70 rounded-lg px-3 py-2 text-xs text-white space-y-0.5">
                  <div>Frame: {currentDetection.frame_number}</div>
                  {currentDetection.chainage && <div>Ch: {currentDetection.chainage?.toFixed(3)} km</div>}
                  {currentDetection.speed && <div>Speed: {currentDetection.speed} km/h</div>}
                  {currentDetection.latitude && (
                    <div>{currentDetection.latitude?.toFixed(5)}, {currentDetection.longitude?.toFixed(5)}</div>
                  )}
                </div>
              )}
            </div>

            {/* Controls */}
            <div className="card space-y-3">
              {/* Progress bar */}
              <div>
                <input
                  type="range"
                  min={0}
                  max={detections.length - 1}
                  value={detectionIndexRef.current}
                  onChange={e => goTo(Number(e.target.value))}
                  className="w-full accent-blue-500"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>{formatTime(currentTime)}</span>
                  <span>{detectionIndexRef.current + 1} / {detections.length}</span>
                  <span>{formatTime(duration)}</span>
                </div>
              </div>

              {/* Buttons */}
              <div className="flex items-center justify-center gap-4">
                <button onClick={() => goTo(detectionIndexRef.current - 10)} className="btn-secondary p-2">
                  <SkipBack size={18} />
                </button>
                <button
                  onClick={() => setPlaying(!playing)}
                  className="btn-primary px-6 py-2 flex items-center gap-2"
                >
                  {playing ? <Pause size={18} /> : <Play size={18} />}
                  {playing ? 'Pause' : 'Play'}
                </button>
                <button onClick={() => goTo(detectionIndexRef.current + 10)} className="btn-secondary p-2">
                  <SkipForward size={18} />
                </button>
              </div>
            </div>
          </div>

          {/* Detection list */}
          <div className="card overflow-auto max-h-[600px]">
            <h3 className="font-semibold text-white mb-3">Detections</h3>
            <div className="space-y-2">
              {detections.map((det, idx) => (
                <button
                  key={det.id}
                  onClick={() => goTo(idx)}
                  className={`w-full text-left p-3 rounded-lg transition-colors ${
                    currentDetection?.id === det.id
                      ? 'bg-blue-900/40 border border-blue-700'
                      : 'bg-gray-800 hover:bg-gray-750'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-gray-400">Frame {det.frame_number}</span>
                    {det.chainage && <span className="text-xs text-gray-500">{det.chainage?.toFixed(3)} km</span>}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {det.detections?.slice(0, 3).map((d, i) => (
                      <span
                        key={i}
                        className="text-xs px-1.5 py-0.5 rounded"
                        style={{
                          background: (CLASS_COLORS[d.normalized_class] || CLASS_COLORS.default) + '33',
                          color: CLASS_COLORS[d.normalized_class] || CLASS_COLORS.default,
                          border: `1px solid ${CLASS_COLORS[d.normalized_class] || CLASS_COLORS.default}44`
                        }}
                      >
                        {d.normalized_class?.replace(/_/g, ' ')}
                      </span>
                    ))}
                    {det.detections?.length > 3 && (
                      <span className="text-xs text-gray-500">+{det.detections.length - 3}</span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
