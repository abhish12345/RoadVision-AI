/**
 * Circular progress ring — used for Road Health Score display.
 */
export default function ProgressRing({ score, size = 100, strokeWidth = 8 }) {
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (score / 100) * circumference

  const color =
    score >= 70 ? '#22c55e' :
    score >= 40 ? '#f59e0b' :
    '#ef4444'

  const label =
    score >= 70 ? 'Good' :
    score >= 40 ? 'Fair' :
    'Poor'

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="-rotate-90">
        {/* Background ring */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="#1e293b" strokeWidth={strokeWidth}
        />
        {/* Progress ring */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.6s ease' }}
        />
      </svg>
      <div className="absolute text-center">
        <div className="text-xl font-bold text-white leading-none">{score.toFixed(0)}</div>
        <div className="text-xs mt-0.5" style={{ color }}>{label}</div>
      </div>
    </div>
  )
}
