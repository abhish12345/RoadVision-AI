import { useEffect, useState, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { getTask, getTaskStats, uploadVideo, getVideoProgress, deleteTask, downloadReport, pauseVideo, resumeVideo, cancelVideo } from '../api'
import toast from 'react-hot-toast'
import {
  ArrowLeft, Upload, Camera, Map, Image, BarChart3,
  Trash2, Download, RefreshCw, CheckCircle, AlertCircle,
  Clock, Zap, Activity, Pause, Play, X
} from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'

const PAVE_CLASSES = ['pothole', 'alligator_crack', 'longitudinal_crack', 'transverse_crack', 'patching', 'bleeding_ravelling']
const ROW_CLASSES = ['road_sign', 'crash_barrier', 'km_stone', 'street_light', 'drain', 'culvert_bridge', 'retaining_wall', 'utility_lines', 'encroachment', 'hazard_marker']
const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#f97316', '#84cc16', '#ec4899', '#14b8a6']

const HEALTH_COLOR = (s) => s >= 70 ? '#22c55e' : s >= 40 ? '#f59e0b' : '#ef4444'

export default function TaskDetail() {
  const { taskId } = useParams()
  const navigate = useNavigate()
  const [task, setTask] = useState(null)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [processingProgress, setProcessingProgress] = useState({})
  const [cameraType, setCameraType] = useState('pave')
  const [captureMode, setCaptureMode] = useState('interval')
  const [captureInterval, setCaptureInterval] = useState(10)
  const [notifEmail, setNotifEmail] = useState('')
  const pollingRef = useRef({})

  const load = async () => {
    try {
      const [taskRes, statsRes] = await Promise.all([
        getTask(taskId),
        getTaskStats(taskId).catch(() => ({ data: null }))
      ])
      setTask(taskRes.data)
      setStats(statsRes.data)
    } catch {
      toast.error('Failed to load task')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    return () => Object.values(pollingRef.current).forEach(clearInterval)
  }, [taskId])

  const startPolling = (videoId) => {
    if (pollingRef.current[videoId]) return
    pollingRef.current[videoId] = setInterval(async () => {
      try {
        const res = await getVideoProgress(videoId)
        setProcessingProgress(prev => ({ ...prev, [videoId]: res.data }))
        if (['completed', 'failed'].includes(res.data.status)) {
          clearInterval(pollingRef.current[videoId])
          delete pollingRef.current[videoId]
          load()
        }
      } catch {}
    }, 2000)
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'video/*': ['.mp4', '.avi', '.mov', '.mkv'] },
    maxFiles: 1,
    onDrop: async (files) => {
      if (!files[0]) return
      setUploading(true)
      setUploadProgress(0)
      const fd = new FormData()
      fd.append('task_id', taskId)
      fd.append('camera_type', cameraType)
      fd.append('capture_mode', captureMode)
      fd.append('capture_interval', captureInterval)
      fd.append('notification_email', notifEmail)
      fd.append('file', files[0])
      try {
        const res = await uploadVideo(fd, setUploadProgress)
        toast.success('Video uploaded! Processing started.')
        startPolling(res.data.video_id)
        load()
      } catch (err) {
        toast.error(err.response?.data?.detail || 'Upload failed')
      } finally {
        setUploading(false)
        setUploadProgress(0)
      }
    }
  })

  const handleDelete = async () => {
    if (!confirm(`Delete task "${task?.name}" and ALL data?`)) return
    try {
      await deleteTask(taskId)
      toast.success('Task deleted')
      navigate('/tasks')
    } catch {
      toast.error('Failed to delete')
    }
  }

  const handlePause = async (videoId) => {
    try {
      await pauseVideo(videoId)
      toast.success('Processing paused')
      load()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to pause')
    }
  }

  const handleResume = async (videoId) => {
    try {
      const res = await resumeVideo(videoId)
      toast.success('Processing resumed')
      startPolling(videoId)
      load()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to resume')
    }
  }

  const handleCancel = async (videoId, videoName) => {
    if (!confirm(`Cancel processing of "${videoName}"? Already detected frames will be kept.`)) return
    try {
      const res = await cancelVideo(videoId)
      toast.success(`Cancelled. ${res.data.frames_detected_so_far} frames already detected are preserved.`)
      load()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to cancel')
    }
  }

  if (loading) return <div className="p-6 text-gray-500">Loading...</div>
  if (!task) return <div className="p-6 text-red-400">Task not found</div>

  const processingVideos = task.videos?.filter(v => v.status === 'processing' || v.status === 'queued') || []
  processingVideos.forEach(v => startPolling(v.id))

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button onClick={() => navigate('/tasks')} className="flex items-center gap-2 text-gray-400 hover:text-white mb-2 text-sm">
            <ArrowLeft size={14} /> Tasks
          </button>
          <h1 className="text-2xl font-bold text-white">{task.name}</h1>
          <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
            <span>{task.nh_number}</span>
            <span>•</span>
            <span>{task.section_code}</span>
            <span>•</span>
            <span>{task.survey_date || 'No date'}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} className="btn-secondary p-2"><RefreshCw size={16} /></button>
          <button onClick={handleDelete} className="btn-danger flex items-center gap-2">
            <Trash2 size={15} /> Delete Task
          </button>
        </div>
      </div>

      {/* Health Score + Quick Links */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {task.road_health_score != null && (
          <div className="card col-span-1">
            <div className="text-xs text-gray-500 mb-1">Road Health Score</div>
            <div className="text-3xl font-bold" style={{ color: HEALTH_COLOR(task.road_health_score) }}>
              {task.road_health_score.toFixed(0)}<span className="text-lg text-gray-500">/100</span>
            </div>
          </div>
        )}
        {[
          { to: `/tasks/${taskId}/gallery`, icon: Image, label: 'Image Gallery', color: 'text-purple-400' },
          { to: `/tasks/${taskId}/map`, icon: Map, label: 'Map View', color: 'text-green-400' },
          { to: `/tasks/${taskId}/reports`, icon: BarChart3, label: 'Reports', color: 'text-blue-400' },
          { to: `/tasks/${taskId}/player?videoId=${task.videos?.[0]?.id || ''}`, icon: Zap, label: 'AI Replay', color: 'text-yellow-400' },
        ].map(({ to, icon: Icon, label, color }) => (
          <Link key={to} to={to} className="card hover:border-gray-700 flex items-center gap-3 transition-colors">
            <Icon size={22} className={color} />
            <span className="text-sm font-medium text-gray-300">{label}</span>
          </Link>
        ))}
      </div>

      {/* Upload Section */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-white flex items-center gap-2">
          <Upload size={18} className="text-blue-400" /> Upload Video
        </h2>

        {/* Camera type selection */}
        <div>
          <label className="label">Camera Type</label>
          <div className="grid grid-cols-2 gap-3">
            {[
              { value: 'pave', label: 'PAVE Camera', desc: 'Pavement defects (cracks, potholes)', icon: '🛣️' },
              { value: 'row', label: 'ROW Camera', desc: 'Road assets (signs, barriers, drains)', icon: '🚧' },
            ].map(opt => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setCameraType(opt.value)}
                className={`p-4 rounded-xl border-2 text-left transition-all ${
                  cameraType === opt.value
                    ? 'border-blue-500 bg-blue-900/20'
                    : 'border-gray-700 bg-gray-800 hover:border-gray-600'
                }`}
              >
                <div className="text-2xl mb-1">{opt.icon}</div>
                <div className="font-medium text-white text-sm">{opt.label}</div>
                <div className="text-xs text-gray-500 mt-0.5">{opt.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Capture settings */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Capture Mode</label>
            <select
              className="input"
              value={captureMode}
              onChange={e => setCaptureMode(e.target.value)}
            >
              <option value="interval">Every N meters</option>
              <option value="fps">Every N fps</option>
            </select>
          </div>
          <div>
            <label className="label">{captureMode === 'interval' ? 'Interval (meters)' : 'FPS'}</label>
            <input
              type="number"
              className="input"
              value={captureInterval}
              min={captureMode === 'interval' ? 5 : 1}
              max={captureMode === 'interval' ? 100 : 30}
              onChange={e => setCaptureInterval(Number(e.target.value))}
            />
          </div>
        </div>

        <div>
          <label className="label">Notification Email (optional)</label>
          <input
            type="email"
            className="input"
            placeholder="Get notified when done"
            value={notifEmail}
            onChange={e => setNotifEmail(e.target.value)}
          />
        </div>

        {/* Drop zone */}
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
            isDragActive ? 'border-blue-500 bg-blue-900/10' : 'border-gray-700 hover:border-gray-600'
          } ${uploading ? 'pointer-events-none opacity-60' : ''}`}
        >
          <input {...getInputProps()} />
          <Upload size={32} className="text-gray-600 mx-auto mb-3" />
          {uploading ? (
            <div>
              <p className="text-gray-400 text-sm mb-2">Uploading... {uploadProgress}%</p>
              <div className="w-full bg-gray-800 rounded-full h-2">
                <div className="bg-blue-500 h-2 rounded-full transition-all" style={{ width: `${uploadProgress}%` }} />
              </div>
            </div>
          ) : isDragActive ? (
            <p className="text-blue-400 text-sm">Drop the video here</p>
          ) : (
            <>
              <p className="text-gray-400 text-sm">Drag & drop a video, or click to browse</p>
              <p className="text-gray-600 text-xs mt-1">MP4, AVI, MOV, MKV supported</p>
            </>
          )}
        </div>
      </div>

      {/* Videos list */}
      {task.videos && task.videos.length > 0 && (
        <div className="card space-y-3">
          <h2 className="font-semibold text-white">Videos ({task.videos.length})</h2>
          {task.videos.map(video => {
            const prog = processingProgress[video.id]
            const progress = prog?.progress ?? video.progress ?? 0
            const status = prog?.status ?? video.status

            return (
              <div key={video.id} className="bg-gray-800 rounded-xl p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-white truncate">{video.original_filename}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        status === 'completed'  ? 'bg-green-900 text-green-300' :
                        status === 'processing' ? 'bg-blue-900 text-blue-300 animate-pulse' :
                        status === 'paused'     ? 'bg-yellow-900 text-yellow-300' :
                        status === 'cancelled'  ? 'bg-gray-700 text-gray-400' :
                        status === 'failed'     ? 'bg-red-900 text-red-300' :
                        'bg-gray-700 text-gray-400'
                      }`}>{status}</span>
                      <span className="text-xs bg-gray-700 text-gray-400 px-2 py-0.5 rounded-full uppercase">
                        {video.camera_type}
                      </span>
                    </div>
                    <div className="text-xs text-gray-500 mt-1 flex gap-3 flex-wrap">
                      <span>{(video.file_size / 1024 / 1024).toFixed(1)} MB</span>
                      <span>{video.total_frames_extracted || 0} frames</span>
                      <span>{video.total_detections || 0} detections</span>
                      {video.chainage_start != null && (
                        <span>Ch: {video.chainage_start?.toFixed(3)} – {video.chainage_end?.toFixed(3)} km</span>
                      )}
                    </div>
                  </div>

                  {/* Action buttons */}
                  <div className="flex items-center gap-1.5 ml-3 flex-shrink-0">
                    {/* Pause — only when processing */}
                    {(status === 'processing' || status === 'queued') && (
                      <button
                        onClick={() => handlePause(video.id)}
                        className="flex items-center gap-1 bg-yellow-700 hover:bg-yellow-600 text-white text-xs px-2.5 py-1.5 rounded-lg transition-colors"
                        title="Pause processing"
                      >
                        <Pause size={12} /> Pause
                      </button>
                    )}

                    {/* Resume — only when paused */}
                    {status === 'paused' && (
                      <button
                        onClick={() => handleResume(video.id)}
                        className="flex items-center gap-1 bg-green-700 hover:bg-green-600 text-white text-xs px-2.5 py-1.5 rounded-lg transition-colors"
                        title="Resume processing"
                      >
                        <Play size={12} /> Resume
                      </button>
                    )}

                    {/* Cancel — when processing or paused */}
                    {(status === 'processing' || status === 'queued' || status === 'paused') && (
                      <button
                        onClick={() => handleCancel(video.id, video.original_filename)}
                        className="flex items-center gap-1 bg-red-800 hover:bg-red-700 text-white text-xs px-2.5 py-1.5 rounded-lg transition-colors"
                        title="Cancel processing (keeps detected frames)"
                      >
                        <X size={12} /> Cancel
                      </button>
                    )}

                    {/* Download report — when completed or cancelled */}
                    {(status === 'completed' || status === 'cancelled') && video.total_detections > 0 && (
                      <button
                        onClick={() => downloadReport(video.id)}
                        className="btn-secondary flex items-center gap-1.5 text-xs py-1.5"
                      >
                        <Download size={13} /> Report
                      </button>
                    )}
                  </div>
                </div>

                {/* Progress bar — processing or paused */}
                {(status === 'processing' || status === 'queued' || status === 'paused') && (
                  <div className="mt-3">
                    <div className="flex justify-between text-xs text-gray-500 mb-1">
                      <span>
                        {status === 'paused'
                          ? `⏸ Paused at ${progress}%`
                          : prog?.status || 'Processing...'}
                      </span>
                      <span>{progress}%</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-1.5">
                      <div
                        className={`h-1.5 rounded-full transition-all ${
                          status === 'paused' ? 'bg-yellow-500' : 'bg-blue-500'
                        }`}
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                    {status === 'paused' && (
                      <div className="text-xs text-yellow-400 mt-1">
                        ⏸ Processing paused — click Resume to continue
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Stats */}
      {stats && stats.class_distribution?.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card">
            <h3 className="font-semibold text-white mb-4">Detection Distribution</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={stats.class_distribution.slice(0, 8)}>
                <XAxis dataKey="class" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {stats.class_distribution.slice(0, 8).map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <h3 className="font-semibold text-white mb-4">Detections along Chainage</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={stats.chainage_data?.slice(0, 20)}>
                <XAxis dataKey="chainage" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
                <Bar dataKey="detections" fill="#3b82f6" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
