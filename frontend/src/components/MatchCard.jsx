function getLiveCardText(match) {
  const status = `${match?.short_detail || ''} ${match?.status || ''}`.toLowerCase()
  if (status.includes('half time') || status.includes('halftime') || status.includes('ht')) return 'Half Time'
  return match?.clock || match?.short_detail || 'LIVE'
}

// One card for all three sidebar variants (live/finished/scheduled) — they differ only
// in status text/styling, whether a scoreline or "vs" shows, and whether kickoff time
// is shown, so a single component with a `variant` prop replaces three near-duplicate blocks.
export default function MatchCard({ match, variant, onClick, isFlashing }) {
  const isLive = variant === 'live'
  const isScheduled = variant === 'scheduled'

  const statusText = isLive ? getLiveCardText(match) : isScheduled ? match.status : 'FULL TIME'
  const statusClass = isLive ? 'match-status live-badge live-clock' : 'match-status'
  const statusEl = <div className={statusClass}>{statusText}</div>

  return (
    <div className={`match-card${isLive ? ' live' : ''}`} onClick={onClick} style={{ cursor: 'pointer' }}>
      {isScheduled ? statusEl : <div className="match-topline">{statusEl}</div>}

      <div className="match-team">
        {match.home.logo && <img src={match.home.logo} alt={match.home.name} className="team-logo" />}
        <span>{match.home.name}</span>
      </div>

      {isScheduled ? (
        <div className="match-vs">vs</div>
      ) : (
        <div className={`scoreline${isFlashing ? ' score-flash' : ''}`}>
          {match.home_score ?? '0'} - {match.away_score ?? '0'}
        </div>
      )}

      <div className="match-team">
        {match.away.logo && <img src={match.away.logo} alt={match.away.name} className="team-logo" />}
        <span>{match.away.name}</span>
      </div>

      <div className="match-details">
        {isScheduled && (
          <div className="match-time">
            {match.date
              ? new Date(match.date).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
              : 'TBD'}
          </div>
        )}
        {match.venue && <div className="match-venue">{match.venue}</div>}
      </div>
    </div>
  )
}
