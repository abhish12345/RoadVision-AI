/**
 * Reusable stat card with icon, value, label, and optional trend.
 */
export default function StatCard({ icon: Icon, label, value, color = 'text-blue-400', bg = 'bg-blue-900/30', trend }) {
  return (
    <div className="card flex items-center gap-4">
      <div className={`${bg} p-3 rounded-lg flex-shrink-0`}>
        <Icon size={22} className={color} />
      </div>
      <div className="min-w-0">
        <div className="text-2xl font-bold text-white truncate">{value}</div>
        <div className="text-xs text-gray-500">{label}</div>
        {trend !== undefined && (
          <div className={`text-xs mt-0.5 ${trend >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {trend >= 0 ? '▲' : '▼'} {Math.abs(trend).toFixed(1)}% vs last
          </div>
        )}
      </div>
    </div>
  )
}
