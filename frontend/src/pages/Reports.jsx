import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getTask, getTaskStats, downloadExcelReport, downloadPdfReport, downloadCsvReport, downloadKmlReport, downloadGeoJsonReport } from '../api'
import { ArrowLeft, Download, BarChart3, TrendingUp, AlertTriangle, CheckCircle, FileSpreadsheet, FileText, Map, Globe } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, PieChart, Pie, Cell, Legend,
} from 'recharts'

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#f97316', '#84cc16']
const HEALTH_COLOR = (s) => s >= 70 ? '#22c55e' : s >= 40 ? '#f59e0b' : '#ef4444'

const IRI_THRESHOLDS = [
  { label: 'Very Good', max: 2, color: '#22c55e' },
  { label: 'Good', max: 4, color: '#84cc16' },
  { label: 'Fair', max: 6, color: '#f59e0b' },
  { label: 'Poor', max: 8, color: '#f97316' },
  { label: 'Very Poor', max: 99, color: '#ef4444' },
]

export default function Reports() {
  const { taskId } = useParams()
  const [task, setTask] = useState(null)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getTask(taskId), getTaskStats(taskId).catch(() => ({ data: null }))]).then(([t, s]) => {
      setTask(t.data)
      setStats(s.data)
      setLoading(false)
    })
  }, [taskId])

  if (loading) return <div className="p-6 text-gray-500">Loading...</div>
  if (!task) return <div className="p-6 text-red-400">Task not found</div>

  const completedVideos = task.videos?.filter(v => v.status === 'completed') || []
  const cameraTypes = [...new Set(completedVideos.map(v => v.camera_type))]
  const isPave = cameraTypes.includes('pave')
  const isRow = cameraTypes.includes('row')

  // IRI distribution from chainage data
  const iriData = stats?.chainage_data?.map(d => ({
    chainage: d.chainage,
    iri: Math.max(0.5, 2 + (d.detections / 5)),
    detections: d.detections,
  })) || []

  // Condition distribution
  const conditionData = IRI_THRESHOLDS.map(t => ({
    name: t.label,
    count: iriData.filter(d => d.iri < t.max && d.iri >= (IRI_THRESHOLDS[IRI_THRESHOLDS.indexOf(t) - 1]?.max || 0)).length,
    color: t.color,
  })).filter(d => d.count > 0)

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link to={`/tasks/${taskId}`} className="flex items-center gap-2 text-gray-400 hover:text-white mb-2 text-sm">
            <ArrowLeft size={14} /> Back to Task
          </Link>
          <h1 className="text-2xl font-bold text-white">Reports — {task.name}</h1>
          <p className="text-gray-500 text-sm">{task.nh_number} • {task.section_code} • {task.survey_date}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {[
            { label: 'Excel (RIS)', icon: FileSpreadsheet, action: () => downloadExcelReport(taskId), color: 'bg-green-700 hover:bg-green-600' },
            { label: 'PDF Report', icon: FileText, action: () => downloadPdfReport(taskId), color: 'bg-red-700 hover:bg-red-600' },
            { label: 'CSV Data', icon: Download, action: () => downloadCsvReport(taskId), color: 'bg-blue-700 hover:bg-blue-600' },
            { label: 'KML (Google Earth)', icon: Map, action: () => downloadKmlReport(taskId), color: 'bg-yellow-700 hover:bg-yellow-600' },
            { label: 'GeoJSON', icon: Globe, action: () => downloadGeoJsonReport(taskId), color: 'bg-purple-700 hover:bg-purple-600' },
          ].map(({ label, icon: Icon, action, color }) => (
            <button key={label} onClick={action}
              className={`${color} text-white text-sm font-medium px-3 py-2 rounded-lg flex items-center gap-2 transition-colors`}>
              <Icon size={15} /> {label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            label: 'Road Health Score',
            value: task.road_health_score ? `${task.road_health_score.toFixed(0)}/100` : 'N/A',
            icon: CheckCircle,
            color: task.road_health_score ? HEALTH_COLOR(task.road_health_score) : '#94a3b8',
          },
          {
            label: 'Total Frames',
            value: stats?.total_frames?.toLocaleString() || 0,
            icon: BarChart3,
            color: '#3b82f6',
          },
          {
            label: 'Total Detections',
            value: stats?.total_detections?.toLocaleString() || 0,
            icon: AlertTriangle,
            color: '#f59e0b',
          },
          {
            label: 'Chainage Covered',
            value: completedVideos.length > 0
              ? `${Math.min(...completedVideos.map(v => v.chainage_start || 999)).toFixed(1)} – ${Math.max(...completedVideos.map(v => v.chainage_end || 0)).toFixed(1)} km`
              : 'N/A',
            icon: TrendingUp,
            color: '#22c55e',
          },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="card">
            <div className="flex items-center gap-2 mb-2">
              <Icon size={16} style={{ color }} />
              <span className="text-xs text-gray-500">{label}</span>
            </div>
            <div className="text-xl font-bold text-white">{value}</div>
          </div>
        ))}
      </div>

      {/* PAVE Reports */}
      {isPave && (
        <div className="space-y-6">
          <h2 className="text-lg font-semibold text-white border-b border-gray-800 pb-2">
            🛣️ PAVE Camera Analysis
          </h2>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* IRI Line Chart */}
            {iriData.length > 0 && (
              <div className="card">
                <h3 className="font-medium text-white mb-4">IRI (Roughness) along Chainage</h3>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={iriData.slice(0, 30)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="chainage" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                    <YAxis domain={[0, 10]} tick={{ fill: '#94a3b8', fontSize: 10 }} label={{ value: 'IRI (m/km)', angle: -90, position: 'insideLeft', fill: '#94a3b8', fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
                    {/* Threshold lines */}
                    <Line type="monotone" dataKey="iri" stroke="#3b82f6" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
                {/* IRI legend */}
                <div className="flex flex-wrap gap-2 mt-2">
                  {IRI_THRESHOLDS.map(t => (
                    <div key={t.label} className="flex items-center gap-1 text-xs text-gray-500">
                      <div className="w-2 h-2 rounded-full" style={{ background: t.color }} />
                      {t.label} (&lt;{t.max})
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Defect Distribution */}
            {stats?.class_distribution?.length > 0 && (
              <div className="card">
                <h3 className="font-medium text-white mb-4">Defect Type Distribution</h3>
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={stats.class_distribution.slice(0, 6)}
                      dataKey="count"
                      nameKey="class"
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      label={({ name, percent }) => `${name?.replace(/_/g, ' ')} ${(percent * 100).toFixed(0)}%`}
                      labelLine={false}
                    >
                      {stats.class_distribution.slice(0, 6).map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Condition Distribution */}
            {conditionData.length > 0 && (
              <div className="card">
                <h3 className="font-medium text-white mb-4">Road Condition Distribution</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={conditionData}>
                    <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {conditionData.map((d, i) => <Cell key={i} fill={d.color} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Detections per chainage */}
            {stats?.chainage_data?.length > 0 && (
              <div className="card">
                <h3 className="font-medium text-white mb-4">Defect Density along Chainage</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={stats.chainage_data.slice(0, 25)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="chainage" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
                    <Bar dataKey="detections" fill="#ef4444" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ROW Reports */}
      {isRow && (
        <div className="space-y-6">
          <h2 className="text-lg font-semibold text-white border-b border-gray-800 pb-2">
            🚧 ROW Camera — Asset Inventory
          </h2>

          {stats?.class_distribution?.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="card">
                <h3 className="font-medium text-white mb-4">Asset Type Distribution</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={stats.class_distribution} layout="vertical">
                    <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                    <YAxis dataKey="class" type="category" tick={{ fill: '#94a3b8', fontSize: 10 }} width={120} />
                    <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                      {stats.class_distribution.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="card">
                <h3 className="font-medium text-white mb-4">Asset Summary Table</h3>
                <div className="overflow-auto max-h-64">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-800">
                        <th className="text-left py-2 text-gray-400 font-medium">Asset Type</th>
                        <th className="text-right py-2 text-gray-400 font-medium">Count</th>
                        <th className="text-right py-2 text-gray-400 font-medium">Avg Conf.</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats.class_distribution.map((d, i) => (
                        <tr key={i} className="border-b border-gray-800/50">
                          <td className="py-2 text-gray-300">{d.class?.replace(/_/g, ' ')}</td>
                          <td className="py-2 text-right text-white font-medium">{d.count}</td>
                          <td className="py-2 text-right text-gray-400">{d.avg_confidence}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {completedVideos.length === 0 && (
        <div className="card text-center py-12">
          <BarChart3 size={40} className="text-gray-700 mx-auto mb-3" />
          <p className="text-gray-500">No completed videos yet. Upload and process a video to see reports.</p>
        </div>
      )}
    </div>
  )
}
