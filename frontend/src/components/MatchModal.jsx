function getMatchPhase(match) {
  const status = `${match?.short_detail || ''} ${match?.status || ''}`.toLowerCase()
  if (status.includes('half time') || status.includes('halftime') || status.includes('ht')) return 'Half Time'
  if (status.includes('full time') || status.includes('ft') || status.includes('final')) return 'FT'
  if (match?.is_live) return 'LIVE'
  return ''
}

function getCenterText(match) {
  const phase = getMatchPhase(match)
  if (phase === 'Half Time') return 'Half Time'
  if (match?.is_live) return match?.clock || match?.short_detail || 'LIVE'
  return match?.date
    ? new Date(match.date).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : 'TBD'
}

export default function MatchModal({ match, teamStats, statsLoading, statsError, onClose }) {
  if (!match) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-header-left">
            <h2>Team Comparison</h2>
            {getMatchPhase(match) && <div className="match-phase-tag">{getMatchPhase(match)}</div>}
          </div>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="fixture-banner">
          <div className="fixture-team">
            {match.home.logo && <img src={match.home.logo} alt={match.home.name} className="fixture-logo" />}
            <span>{match.home.name}</span>
          </div>
          <div className="fixture-score">
            <div className="score-text">
              {match.state === 'pre'
                ? 'vs'
                : <>{match.home_score ?? 0} <span className="dash">-</span> {match.away_score ?? 0}</>}
            </div>
            <div className="score-sub">{getCenterText(match)}</div>
          </div>
          <div className="fixture-team">
            {match.away.logo && <img src={match.away.logo} alt={match.away.name} className="fixture-logo" />}
            <span>{match.away.name}</span>
          </div>
        </div>

        <div className="fixture-meta">
          <div>{match.status || 'Upcoming fixture'}</div>
          {match.venue && <div>{match.venue}</div>}
        </div>

        {statsLoading && (
          <div className="modal-loading-skeleton" aria-label="Loading team statistics">
            <div className="skeleton-line" />
            <div className="skeleton-line skeleton-line-short" />
            <div className="skeleton-line" />
          </div>
        )}
        {statsError && <div className="modal-error">{statsError}</div>}

        {(match.is_live || match.state === 'post') && Array.isArray(match.scorers) && match.scorers.length > 0 && (
          <div className="scorers-panel">
            <div className="scorers-header">Scorers</div>
            <div className="scorers-rows">
              {match.scorers.map((s, idx) => (
                <div key={idx} className="scorer-entry">
                  <div className="scorer-player">{s.player || s.desc || 'Unknown'}</div>
                  <div className="scorer-meta">{s.team || ''} · <span className="scorer-minute">{s.minute || ''}</span></div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="stats-comparison">
          <div className="team-stats">
            <div className="team-header">
              {match.home.logo && <img src={match.home.logo} alt={match.home.name} className="modal-logo" />}
              <h3>{match.home.name}</h3>
            </div>
            <div className="stat-item">
              <span className="stat-label">Total Wins</span>
              <span className="stat-value">{teamStats?.home?.wins ?? '—'}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Goals Scored</span>
              <span className="stat-value">{teamStats?.home?.goals_scored ?? '—'}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Top Scorer</span>
              <span className="stat-value">{teamStats?.home?.top_scorer ? `${teamStats.home.top_scorer} (${teamStats.home.top_scorer_goals})` : '—'}</span>
            </div>
            {(match.is_live || match.state === 'post') && match.scorers && (
              <div className="scorers-list">
                <div className="scorers-title">Scorers</div>
                {match.scorers.filter(s => s.team && s.team.toLowerCase().includes(match.home.name.toLowerCase())).map((s, idx) => (
                  <div key={idx} className="scorer-row">{s.player || s.desc} <span className="scorer-minute">{s.minute || ''}</span></div>
                ))}
              </div>
            )}
          </div>

          <div className="vs-divider">VS</div>

          <div className="team-stats">
            <div className="team-header">
              {match.away.logo && <img src={match.away.logo} alt={match.away.name} className="modal-logo" />}
              <h3>{match.away.name}</h3>
            </div>
            <div className="stat-item">
              <span className="stat-label">Total Wins</span>
              <span className="stat-value">{teamStats?.away?.wins ?? '—'}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Goals Scored</span>
              <span className="stat-value">{teamStats?.away?.goals_scored ?? '—'}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Top Scorer</span>
              <span className="stat-value">{teamStats?.away?.top_scorer ? `${teamStats.away.top_scorer} (${teamStats.away.top_scorer_goals})` : '—'}</span>
            </div>
            {(match.is_live || match.state === 'post') && match.scorers && (
              <div className="scorers-list">
                <div className="scorers-title">Scorers</div>
                {match.scorers.filter(s => s.team && s.team.toLowerCase().includes(match.away.name.toLowerCase())).map((s, idx) => (
                  <div key={idx} className="scorer-row">{s.player || s.desc} <span className="scorer-minute">{s.minute || ''}</span></div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
