import { useMemo } from 'react'
import MatchCard from './MatchCard'

export default function MatchSidebar({ upcoming, flashingMatches, onMatchClick }) {
  const liveMatches = useMemo(() => (upcoming || []).filter(match => match.is_live), [upcoming])
  const finishedMatches = useMemo(() => (upcoming || []).filter(match => !match.is_live && match.state === 'post'), [upcoming])
  const scheduledMatches = useMemo(() => (upcoming || []).filter(match => !match.is_live && match.state === 'pre'), [upcoming])

  return (
    <div className="sidebar">
      <div className="sidebar-header">Today's Matches</div>
      {upcoming && upcoming.length === 0 ? (
        <p className="muted">No matches today.</p>
      ) : upcoming ? (
        <>
          {liveMatches.length > 0 && (
            <div className="match-group">
              <div className="match-group-title live-title">Live Now</div>
              <div className="matches-list">
                {liveMatches.map((m, i) => (
                  <MatchCard
                    key={`live-${i}`}
                    match={m}
                    variant="live"
                    onClick={() => onMatchClick(m)}
                    isFlashing={!!flashingMatches[`${m.home?.name}-${m.away?.name}`]}
                  />
                ))}
              </div>
            </div>
          )}

          {finishedMatches.length > 0 && (
            <div className="match-group">
              <div className="match-group-title">Finished Today</div>
              <div className="matches-list">
                {finishedMatches.map((m, i) => (
                  <MatchCard key={`finished-${i}`} match={m} variant="finished" onClick={() => onMatchClick(m)} />
                ))}
              </div>
            </div>
          )}

          {scheduledMatches.length > 0 && (
            <div className="match-group">
              <div className="match-group-title">Upcoming Fixtures</div>
              <div className="matches-list">
                {scheduledMatches.map((m, i) => (
                  <MatchCard key={`upcoming-${i}`} match={m} variant="scheduled" onClick={() => onMatchClick(m)} />
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        <p className="muted">Loading…</p>
      )}
    </div>
  )
}
