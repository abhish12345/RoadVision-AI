import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getTasks, deleteTask } from '../api'
import { Plus, Trash2, Eye, Camera, ChevronRight, Search } from 'lucide-react'
import toast from 'react-hot-toast'

const STATUS_BADGE = {
  completed: 'bg-green-900 text-green-300',
  processing: 'bg-blue-900 text-blue-300 animate-pulse',
  failed: 'bg-red-900 text-red-300',
  created: 'bg-gray-800 text-gray-400',
  queued: 'bg-yellow-900 text-yellow-300',
}

export default function Tasks() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [deleting, setDeleting] = useState(null)

  const load = () => {
    getTasks().then(r => { setTasks(r.data); setLoading(false) })
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (task) => {
    if (!confirm(`Delete task "${task.name}" and ALL its data? This cannot be undone.`)) return
    setDeleting(task.id)
    try {
      await deleteTask(task.id)
      toast.success('Task deleted')
      load()
    } catch {
      toast.error('Failed to delete task')
    } finally {
      setDeleting(null)
    }
  }

  const filtered = tasks.filter(t =>
    t.name.toLowerCase().includes(search.toLowerCase()) ||
    (t.nh_number || '').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Survey Tasks</h1>
          <p className="text-gray-500 text-sm mt-1">{tasks.length} total tasks</p>
        </div>
        <Link to="/tasks/new" className="btn-primary flex items-center gap-2">
          <Plus size={16} /> New Task
        </Link>
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
        <input
          className="input pl-9"
          placeholder="Search tasks..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {loading ? (
        <div className="text-gray-500 text-sm">Loading tasks...</div>
      ) : filtered.length === 0 ? (
        <div className="card text-center py-16">
          <Camera size={40} className="text-gray-700 mx-auto mb-3" />
          <p className="text-gray-400 font-medium">No tasks found</p>
          <p className="text-gray-600 text-sm mt-1">Create a new task to start a road survey</p>
          <Link to="/tasks/new" className="btn-primary inline-flex items-center gap-2 mt-4">
            <Plus size={16} /> Create Task
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(task => (
            <div key={task.id} className="card hover:border-gray-700 transition-colors">
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3">
                    <h3 className="font-semibold text-white truncate">{task.name}</h3>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[task.status]}`}>
                      {task.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
                    <span>{task.nh_number || 'No NH'}</span>
                    <span>{task.section_code || 'No section'}</span>
                    <span>{task.survey_date || 'No date'}</span>
                    <span>{task.video_count || 0} video(s)</span>
                    {task.road_health_score != null && (
                      <span className="font-medium text-blue-400">
                        Health: {task.road_health_score.toFixed(0)}/100
                      </span>
                    )}
                  </div>
                  {task.description && (
                    <p className="text-xs text-gray-600 mt-1 truncate">{task.description}</p>
                  )}
                </div>
                <div className="flex items-center gap-2 ml-4">
                  <Link
                    to={`/tasks/${task.id}`}
                    className="btn-secondary flex items-center gap-1.5 text-sm py-1.5"
                  >
                    <Eye size={14} /> View
                  </Link>
                  <button
                    onClick={() => handleDelete(task)}
                    disabled={deleting === task.id}
                    className="btn-danger flex items-center gap-1.5 text-sm py-1.5"
                  >
                    <Trash2 size={14} />
                    {deleting === task.id ? '...' : 'Delete'}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
