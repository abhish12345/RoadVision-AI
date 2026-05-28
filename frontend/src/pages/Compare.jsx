import { useEffect, useState } from 'react'
import { getTasks, getTaskStats } from '../api'
import { GitCompare, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, Legend } from 'recharts'

const HEALTH_COLOR = (s) => s >= 70 ? '#22c55e' : s >= 40 ? '#f59e0b' : '#ef4444'

export default function Compare() {
  const [tasks, setTasks] = useState([])
  const [taskA, setTaskA] = useState('')
  const [taskB, setTaskB] = useState('')
  const [statsA, setStatsA] = useState(null)
  const [statsB, setStatsB] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    getTasks().then(r => setTasks(r.data.filter(t => t.status === 'completed')))
  }, [])

  const compare = async () => {
    if (!taskA || !taskB) return
    setLoading(true)
    const [a, b] = await Promise.all([getTaskStats(taskA), getTaskStats(taskB)])
    setStatsA(a.data)
    setStatsB(b.data)
    setLoading(false)
  }

  const taskAInfo = tasks.find(t => t.id === taskA)
  const taskBInfo = tasks.find(t => t.id === taskB)

  // Build comparison chart data
  const comparisonData = statsA && statsB ? (() => {
    const allClasses = new Set([
      ...statsA.class_distribution.map(d => d.class),
      ...statsB.class_distribution.map(d => d.class),
    ])
    return Array.from(allClasses).map(cls => ({
      class: cls?.replace(/_/g, ' '),
      [taskAInfo?.name?.slice(0, 12) || 'Task A']: statsA.class_distribution.find(d => d.class === cls)?.count || 0,
      [taskBInfo?.name?.slice(0, 12) || 'Task B']: statsB.class_distribution.find(d => d.class === cls)?.count || 0,
    }))
  })() : []

  const scoreDiff = statsA && statsB && taskAInfo && taskBInfo
    ? (taskBInfo.road_health_score || 0) - (taskAInfo.road_health_score || 0)
    : null

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <GitCompare size={24} className="text-blue-400" /> Compare Tasks
        </h1>
        <p className="text-gray-500 text-sm mt-1">Compare two survey tasks side by side</p>
      </div>

      {/* Task Selection */}
      <div className="card grid grid-cols-1 lg:grid-cols-3 gap-4 items-end">
        <div>
          <label className="label">Task A (Baseline)</label>
          <select className="input" value={taskA} onChange={e => setTaskA(e.target.value)}>
            <option value="">Select task...</option>
            {tasks.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Task B (Compare)</label>
          <select className="input" value={taskB} onChange={e => setTaskB(e.target.value)}>
            <option value="">Select task...</option>
            {tasks.filter(t => t.id !== taskA).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <button
          onClick={compare}
          disabled={!taskA || !taskB || loading}
          className="btn-primary"
        >
          {loading ? 'Comparing...' : 'Compare'}
        </button>
      </div>

      {statsA && statsB && (
        <>
          {/* Score comparison */}
          <div className="grid grid-cols-3 gap-4">
            <div className="card text-center">
              <div className="text-xs text-gray-500 mb-1">{taskAInfo?.name?.slice(0, 20)}</div>
              <div className="text-3xl font-bold" style={{ color: HEALTH_COLOR(taskAInfo?.road_health_score || 0) }}>
                {taskAInfo?.road_health_score?.toFixed(0) || 'N/A'}
              </div>
              <div className="text-xs text-gray-600">Health Score</div>
            </div>
            <div className="card text-center flex flex-col items-center justify-center">
              {scoreDiff !== null && (
                <>
                  {scoreDiff > 0 ? <TrendingUp size={28} className="text-green-400" /> :
                   scoreDiff < 0 ? <TrendingDown size={28} className="text-red-400" /> :
                   <Minus size={28} className="text-gray-400" />}
                  <div className={`text-xl font-bold mt-1 ${scoreDiff > 0 ? 'text-green-400' : scoreDiff < 0 ? 'text-red-400' : 'text-gray-400'}`}>
                    {scoreDiff > 0 ? '+' : ''}{scoreDiff.toFixed(1)}
                  </div>
                  <div className="text-xs text-gray-600">Change</div>
                </>
              )}
            </div>
            <div className="card text-center">
              <div className="text-xs text-gray-500 mb-1">{taskBInfo?.name?.slice(0, 20)}</div>
              <div className="text-3xl font-bold" style={{ color: HEALTH_COLOR(taskBInfo?.road_health_score || 0) }}>
                {taskBInfo?.road_health_score?.toFixed(0) || 'N/A'}
              </div>
              <div className="text-xs text-gray-600">Health Score</div>
            </div>
          </div>

          {/* Stats comparison */}
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: 'Total Frames', a: statsA.total_frames, b: statsB.total_frames },
              { label: 'Total Detections', a: statsA.total_detections, b: statsB.total_detections },
            ].map(({ label, a, b }) => (
              <div key={label} className="card">
                <div className="text-xs text-gray-500 mb-3">{label}</div>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-gray-600">{taskAInfo?.name?.slice(0, 15)}</div>
                    <div className="text-xl font-bold text-white">{a?.toLocaleString()}</div>
                  </div>
                  <div className="text-gray-700">vs</div>
                  <div className="text-right">
                    <div className="text-xs text-gray-600">{taskBInfo?.name?.slice(0, 15)}</div>
                    <div className="text-xl font-bold text-white">{b?.toLocaleString()}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Detection comparison chart */}
          {comparisonData.length > 0 && (
            <div className="card">
              <h3 className="font-medium text-white mb-4">Detection Comparison by Class</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={comparisonData}>
                  <XAxis dataKey="class" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
                  <Legend />
                  <Bar dataKey={taskAInfo?.name?.slice(0, 12) || 'Task A'} fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  <Bar dataKey={taskBInfo?.name?.slice(0, 12) || 'Task B'} fill="#22c55e" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}

      {tasks.length === 0 && (
        <div className="card text-center py-12">
          <GitCompare size={40} className="text-gray-700 mx-auto mb-3" />
          <p className="text-gray-500">No completed tasks available for comparison</p>
        </div>
      )}
    </div>
  )
}
