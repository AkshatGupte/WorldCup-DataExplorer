import { useState, useEffect } from 'react'
import LeaderboardCard from './LeaderboardCard'

function LeaderboardsSkeleton() {
  return (
    <div className="leaderboard-grid">
      {[0, 1, 2, 3].map(card => (
        <div className="leaderboard-card" key={card}>
          <div className="skeleton-line skeleton-section-title" />
          <div className="leaderboard-rows" style={{ marginTop: 14 }}>
            {[0, 1, 2, 3, 4].map(row => (
              <div className="skeleton-table-row" key={row} style={{ opacity: 1 - row * 0.15 }} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// Self-contained: fetches its own data the first time it becomes active, rather
// than making the parent own leaderboards state it doesn't otherwise need.
export default function LeaderboardsTab({ active }) {
  const [leaderboards, setLeaderboards] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function loadLeaderboards() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/leaderboards')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setLeaderboards(data)
    } catch (e) {
      setError(e?.message || 'Failed to load leaderboards.')
    }
    setLoading(false)
  }

  useEffect(() => {
    if (active && !leaderboards && !loading) {
      loadLeaderboards()
    }
  }, [active])

  // Stays mounted even when inactive (the parent always renders this component) so
  // its fetched data survives switching tabs and back — only the visible output is
  // gated on `active`, not the component instance or its state.
  if (!active) return null

  return (
    <div className="tab-fade-in" style={{ padding: "0 24px 24px" }}>
      {loading && <LeaderboardsSkeleton />}
      {error && <div className="error-banner">{error}</div>}
      {leaderboards && (
        <div className="leaderboard-grid">
          <LeaderboardCard title="Top 10 Players by xG" items={leaderboards.top_players_xg} valueFormatter={v => v.toFixed(2)} />
          <LeaderboardCard title="Teams by Highest xG" items={leaderboards.top_teams_xg} valueFormatter={v => v.toFixed(2)} subtitleKey={null} />
          <LeaderboardCard title="Highest Rated Players" items={leaderboards.top_rated_players} valueFormatter={v => v.toFixed(1)} />
          <LeaderboardCard title="Highest Scoring Teams" items={leaderboards.top_scoring_teams} valueFormatter={v => Math.round(v)} subtitleKey={null} />
        </div>
      )}
    </div>
  )
}
