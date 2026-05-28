import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getTasks } from '../api'
import { Activity, Camera, CheckCircle, Clock, AlertTriangle, Plus, TrendingUp, Video } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LineChart, Line, CartesianGrid } from 'recharts'
import StatCard from '../components/StatCard'
import ProgressRing from '../components/ProgressRing'
import ModelStatus from '../components/ModelStatus'

const STATUS_COLORS = {
  completed: 'text-green-400 bg-green-900/30',
  processing: 'text-blue-400 bg-blue-900/30 animate-pulse',
  failed: 'text-red-400 bg-red-900/30',
  created: 'text-gray-400 bg-gray-800',
  queued: 'text-yellow-400 bg-yellow-900/30',
}

const HEALTH_COLOR = (s) => s >= 70 ? '#22c55e' : s >= 40 ? '#f59e0b' : '#ef4444'

export default function Dashboard() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getTasks()
      .then(r => { setTasks(r.data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const stats = {
    total: tasks.length,
    completed: tasks.filter(t => t.status === 'completed').length,
    processing: tasks.filter(t => t.status === 'processing' || t.status === 'queued').length,
    failed: tasks.filter(t => t.status === 'failed').length,
  }

  const healthData = tasks
    .filter(t => t.road_health_score != null)
    .slice(0, 10)
    .map(t => ({ name: t.name.slice(0, 14), score: Math.round(t.road_health_score) }))

  const avgHealth = healthData.length > 0
    ? Math.round(healthData.reduce((s, d) => s + d.score, 0) / healthData.length)
    : null

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">Road Identification System overview</p>
        </div>
        <Link to="/tasks/new" className="btn-primary flex items-center gap-2">
          <Plus size={16} /> New Task
        </Link>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Activity}      label="Total Tasks"  value={stats.total}      color="text-blue-400"   bg="bg-blue-900/30" />
        <StatCard icon={CheckCircle}   label="Completed"    value={stats.completed}  color="text-green-400"  bg="bg-green-900/30" />
        <StatCard icon={Clock}         label="In Progress"  value={stats.processing} color="text-yellow-400" bg="bg-yellow-900/30" />
        <StatCard icon={AlertTriangle} label="Failed"       value={stats.failed}     color="text-red-400"    bg="bg-red-900/30" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Average health score ring */}
        {avgHealth !== null && (
          <div className="card flex flex-col items-center justify-center gap-3">
            <div className="text-sm font-medium text-gray-400">Average Road Health</div>
            <ProgressRing score={avgHealth} size={120} strokeWidth={10} />
            <div className="text-xs text-gray-600">{healthData.length} surveyed tasks</div>
          </div>
        )}

        {/* Health score bar chart */}
        {healthData.length > 0 ? (
          <div className={`card ${avgHealth !== null ? 'lg:col-span-2' : 'lg:col-span-3'}`}>
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp size={16} className="text-blue-400" />
              <h2 className="font-semibold text-white text-sm">Road Health per Task</h2>
            </div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={healthData} barSize={28}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <YAxis domain={[0, 100]} tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                  labelStyle={{ color: '#f1f5f9' }}
                  formatter={(v) => [`${v}/100`, 'Health Score']}
                />
                <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                  {healthData.map((entry, i) => (
                    <Cell key={i} fill={HEALTH_COLOR(entry.score)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="card lg:col-span-2 flex items-center justify-center py-12">
            <div className="text-center">
              <Camera size={36} className="text-gray-700 mx-auto mb-2" />
              <p className="text-gray-500 text-sm">No completed surveys yet</p>
            </div>
          </div>
        )}
      </div>

      {/* AI Model Status */}
      <ModelStatus />

      {/* Recent tasks */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-white">Recent Tasks</h2>
          <Link to="/tasks" className="text-xs text-blue-400 hover:text-blue-300">View all →</Link>
        </div>
        {loading ? (
          <div className="space-y-2">
            {[1,2,3].map(i => <div key={i} className="h-14 bg-gray-800 rounded-lg animate-pulse" />)}
          </div>
        ) : tasks.length === 0 ? (
          <div className="text-center py-10">
            <Video size={36} className="text-gray-700 mx-auto mb-2" />
            <p className="text-gray-500 text-sm">No tasks yet. Create one to start a road survey.</p>
            <Link to="/tasks/new" className="btn-primary inline-flex items-center gap-2 mt-4 text-sm">
              <Plus size={14} /> Create First Task
            </Link>
          </div>
        ) : (
          <div className="space-y-2">
            {tasks.slice(0, 8).map(task => (
              <Link
                key={task.id}
                to={`/tasks/${task.id}`}
                className="flex items-center justify-between p-3 bg-gray-800 rounded-lg hover:bg-gray-700/60 transition-colors group"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-white truncate group-hover:text-blue-300 transition-colors">
                      {task.name}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize flex-shrink-0 ${STATUS_COLORS[task.status]}`}>
                      {task.status}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5 flex gap-3">
                    <span>{task.nh_number || '—'}</span>
                    <span>{task.section_code || '—'}</span>
                    <span>{task.survey_date || 'No date'}</span>
                    <span>{task.video_count || 0} video(s)</span>
                  </div>
                </div>
                {task.road_health_score != null && (
                  <div className="ml-4 flex-shrink-0">
                    <ProgressRing score={task.road_health_score} size={48} strokeWidth={5} />
                  </div>
                )}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
