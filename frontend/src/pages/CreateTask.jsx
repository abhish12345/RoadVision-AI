import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createTask } from '../api'
import toast from 'react-hot-toast'
import { ArrowLeft, Plus } from 'lucide-react'

export default function CreateTask() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    name: '',
    description: '',
    nh_number: 'NH-033',
    section_code: '',
    survey_date: '',
    notification_email: '',
  })
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name.trim()) { toast.error('Task name is required'); return }
    setLoading(true)
    try {
      const res = await createTask(form)
      toast.success('Task created!')
      navigate(`/tasks/${res.data.id}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create task')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-2xl">
      <button onClick={() => navigate('/tasks')} className="flex items-center gap-2 text-gray-400 hover:text-white mb-6 text-sm">
        <ArrowLeft size={16} /> Back to Tasks
      </button>

      <h1 className="text-2xl font-bold text-white mb-6">Create New Survey Task</h1>

      <form onSubmit={handleSubmit} className="card space-y-5">
        <div>
          <label className="label">Task Name *</label>
          <input
            className="input"
            placeholder="e.g. NH-033 Farakka Survey Feb 2026"
            value={form.name}
            onChange={e => setForm({ ...form, name: e.target.value })}
            required
          />
        </div>

        <div>
          <label className="label">Description</label>
          <textarea
            className="input resize-none"
            rows={3}
            placeholder="Optional description..."
            value={form.description}
            onChange={e => setForm({ ...form, description: e.target.value })}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">NH Number</label>
            <input
              className="input"
              placeholder="NH-033"
              value={form.nh_number}
              onChange={e => setForm({ ...form, nh_number: e.target.value })}
            />
          </div>
          <div>
            <label className="label">Section Code</label>
            <input
              className="input"
              placeholder="BAN-KEL"
              value={form.section_code}
              onChange={e => setForm({ ...form, section_code: e.target.value })}
            />
          </div>
        </div>

        <div>
          <label className="label">Survey Date</label>
          <input
            type="date"
            className="input"
            value={form.survey_date}
            onChange={e => setForm({ ...form, survey_date: e.target.value })}
          />
        </div>

        <div>
          <label className="label">Notification Email (optional)</label>
          <input
            type="email"
            className="input"
            placeholder="you@example.com"
            value={form.notification_email}
            onChange={e => setForm({ ...form, notification_email: e.target.value })}
          />
          <p className="text-xs text-gray-600 mt-1">You'll receive an email when processing completes</p>
        </div>

        <div className="flex gap-3 pt-2">
          <button type="submit" disabled={loading} className="btn-primary flex items-center gap-2">
            <Plus size={16} />
            {loading ? 'Creating...' : 'Create Task'}
          </button>
          <button type="button" onClick={() => navigate('/tasks')} className="btn-secondary">
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}
