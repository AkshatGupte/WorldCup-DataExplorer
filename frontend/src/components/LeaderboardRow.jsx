import { useState, useEffect } from 'react'
import { useCountUp } from '../hooks/useCountUp'

// A single leaderboard row as a real component (not a plain function called in a
// loop) — useCountUp is a hook, and hooks can only run inside an actual component
// instance, not inside a .map() callback in a shared parent's render. Bar fill and
// the number both animate in together, staggered per rank for a cascading reveal.
export default function LeaderboardRow({ rank, item, maxValue, subtitleKey, valueFormatter }) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setMounted(true), rank * 60)
    return () => clearTimeout(t)
  }, [rank])
  const animatedValue = useCountUp(mounted ? item.value : 0, 700)
  const pct = Math.max(4, (item.value / maxValue) * 100)

  return (
    <div className="leaderboard-row">
      <div className="leaderboard-rank">{rank}</div>
      <div className="leaderboard-identity">
        <div className="leaderboard-name">{item.name || item.team}</div>
        {item[subtitleKey] && item.name && <div className="leaderboard-subtitle">{item[subtitleKey]}</div>}
      </div>
      <div className="leaderboard-bar-track">
        <div className="leaderboard-bar-fill" style={{ width: mounted ? `${pct}%` : '0%' }} />
      </div>
      <div className="leaderboard-value">{valueFormatter ? valueFormatter(animatedValue) : Math.round(animatedValue)}</div>
    </div>
  )
}
