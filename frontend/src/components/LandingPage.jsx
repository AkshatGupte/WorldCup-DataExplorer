import { useState, useEffect } from 'react'

const TOOLS = [
  {
    tab: 'explorer',
    icon: '🔍',
    title: 'Data Explorer',
    description: 'Ask any question in plain English — matches, standings, player stats — and get a SQL-backed answer with a chart.',
  },
  {
    tab: 'finder',
    icon: '🎯',
    title: 'Player Finder',
    description: 'Filter players by stat thresholds — xG above X, duels won above Y — and get a ranked table back instantly.',
  },
  {
    tab: 'leaderboards',
    icon: '🏆',
    title: 'Leaderboards',
    description: 'Top players and teams by xG, rating, and goals — always up to date, no query needed.',
  },
  {
    tab: 'bracket',
    icon: '⚽',
    title: 'Knockout Bracket',
    description: 'The full Round of 32 through the Final, with live scores and team comparisons on click.',
  },
]

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' })
}

export default function LandingPage({ onNavigate }) {
  const [overview, setOverview] = useState(null)

  useEffect(() => {
    fetch('/tournament-overview')
      .then(res => (res.ok ? res.json() : null))
      .then(setOverview)
      .catch(() => setOverview(null))
  }, [])

  return (
    <div className="tab-fade-in" style={{ padding: '0 24px 32px' }}>
      <div className="tournament-intro">
        <div className="answer-kicker">FIFA World Cup 2026</div>
        <p>
          The 23rd FIFA World Cup is the first ever hosted by three nations at once — the United States,
          Mexico, and Canada — and the first played with an expanded 48-team field, up from 32. Matches
          run {formatDate(overview?.start_date)} through {formatDate(overview?.end_date)}, opening with the
          group stage before narrowing through a new round of 32, then the round of 16, quarter-finals,
          semi-finals, and the final.
        </p>

        <div className="tournament-stats-row">
          <div className="tournament-stat">
            <div className="tournament-stat-value">{overview?.teams ?? '—'}</div>
            <div className="tournament-stat-label">Teams</div>
          </div>
          <div className="tournament-stat">
            <div className="tournament-stat-value">{overview?.matches ?? '—'}</div>
            <div className="tournament-stat-label">Matches</div>
          </div>
          <div className="tournament-stat">
            <div className="tournament-stat-value">{overview?.host_countries ?? '—'}</div>
            <div className="tournament-stat-label">Host nations</div>
          </div>
          <div className="tournament-stat">
            <div className="tournament-stat-value">{overview?.stadiums ?? '—'}</div>
            <div className="tournament-stat-label">Stadiums</div>
          </div>
          <div className="tournament-stat">
            <div className="tournament-stat-value">{overview?.confederations ?? '—'}</div>
            <div className="tournament-stat-label">Confederations</div>
          </div>
        </div>
      </div>

      <div className="landing-grid">
        {TOOLS.map(tool => (
          <button key={tool.tab} className="landing-card" onClick={() => onNavigate(tool.tab)}>
            <div className="landing-card-icon">{tool.icon}</div>
            <div className="landing-card-title">{tool.title}</div>
            <div className="landing-card-description">{tool.description}</div>
            <div className="landing-card-cta">Open →</div>
          </button>
        ))}
      </div>

      <div className="landing-about">
        <div className="answer-kicker">About this project</div>
        <p>
          Every answer here is generated live: your question goes to an LLM that writes SQL against a
          local database of FIFA World Cup 2026 fixtures, standings, and player statistics, then the
          result is verified and — where it helps — charted with Plotly. Leaderboards and Player Finder
          skip the LLM entirely and query the database directly for instant, deterministic results.
        </p>
      </div>
    </div>
  )
}
