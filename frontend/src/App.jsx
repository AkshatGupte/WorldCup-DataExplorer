import { useState, useEffect, useRef } from 'react'
import Bracket from './Bracket'
import SearchPanel from './components/SearchPanel'
import ResultPanel from './components/ResultPanel'
import MatchSidebar from './components/MatchSidebar'
import MatchModal from './components/MatchModal'
import LeaderboardsTab from './components/LeaderboardsTab'
import PlayerFinder from './components/PlayerFinder'
import LandingPage from './components/LandingPage'

export default function App() {
  const [question, setQuestion] = useState('')
  const [answeredQuestion, setAnsweredQuestion] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadingElapsed, setLoadingElapsed] = useState(0)
  const [error, setError] = useState(null)
  const [apiError, setApiError] = useState(null)
  const [upcoming, setUpcoming] = useState(null)
  const [flashingMatches, setFlashingMatches] = useState({})
  const previousScores = useRef({})
  const [selectedMatch, setSelectedMatch] = useState(null)
  const [teamStats, setTeamStats] = useState(null)
  const [statsLoading, setStatsLoading] = useState(false)
  const [statsError, setStatsError] = useState(null)
  const [activeTab, setActiveTab] = useState('home')
  const [showSql, setShowSql] = useState(false)
  const [queryMode, setQueryMode] = useState('general')

  async function loadUpcoming() {
    try {
      const res = await fetch('/today-matches')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const contentType = res.headers.get('content-type') || ''
      if (!contentType.includes('application/json')) {
        throw new Error('Backend returned HTML instead of JSON for today matches')
      }
      const data = await res.json()
      setApiError(null)

      // flash a match's scoreline when its score actually changes between polls —
      // a quiet cue that something just happened without needing a full refresh
      const newlyChanged = []
      for (const m of data) {
        const key = `${m.home?.name}-${m.away?.name}`
        const scoreKey = `${m.home_score ?? ''}-${m.away_score ?? ''}`
        const prev = previousScores.current[key]
        if (prev !== undefined && prev !== scoreKey) newlyChanged.push(key)
        previousScores.current[key] = scoreKey
      }
      if (newlyChanged.length) {
        setFlashingMatches(prev => {
          const next = { ...prev }
          newlyChanged.forEach(k => { next[k] = true })
          return next
        })
        setTimeout(() => {
          setFlashingMatches(prev => {
            const next = { ...prev }
            newlyChanged.forEach(k => { delete next[k] })
            return next
          })
        }, 2200)
      }

      setUpcoming(data)
    } catch (e) {
      console.error('Failed to load today matches', e)
      setApiError("Live match data isn't available right now. If the server was idle, it may take up to a minute to wake up — please try again shortly.")
      setUpcoming([])
    }
  }

  useEffect(() => {
    loadUpcoming()
    const interval = setInterval(loadUpcoming, 15000)
    return () => clearInterval(interval)
  }, [])

  // response times vary a lot here (a few seconds normally, up to a minute if the
  // LLM provider chain has to fail over) — track elapsed time so the loading state
  // can reassure the user instead of looking frozen during a long wait. Reset of
  // loadingElapsed happens in handleSubmit (the event that starts loading), not here —
  // this effect only subscribes to the interval while loading is true.
  useEffect(() => {
    if (!loading) return
    const start = Date.now()
    const interval = setInterval(() => setLoadingElapsed(Math.floor((Date.now() - start) / 1000)), 1000)
    return () => clearInterval(interval)
  }, [loading])

  async function handleSubmit() {
    if (!question.trim()) return
    setLoading(true)
    setLoadingElapsed(0)
    setError(null)
    setApiError(null)
    setShowSql(false)
    try {
      const res = await fetch('/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, mode: queryMode })
      })

      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }

      const contentType = res.headers.get('content-type') || ''
      if (!contentType.includes('application/json')) {
        const text = await res.text()
        throw new Error(text || 'Backend returned HTML instead of JSON')
      }

      const data = await res.json()
      setResult(data)
      setAnsweredQuestion(question.trim())
    } catch (e) {
      setError(e?.message || 'Failed to connect to backend.')
      setResult(null)
      setApiError("We couldn't reach the server. If it was idle, it may take up to a minute to wake up — please try your search again shortly.")
    }
    setLoading(false)
  }

  async function handleMatchClick(match) {
    setSelectedMatch(match)
    setTeamStats(null)
    setStatsError(null)
    setStatsLoading(true)
    try {
      const [homeRes, awayRes] = await Promise.all([
        fetch(`/team-stats/${encodeURIComponent(match.home.name)}`),
        fetch(`/team-stats/${encodeURIComponent(match.away.name)}`)
      ])

      if (!homeRes.ok || !awayRes.ok) throw new Error('Failed to fetch stats')

      const homeType = homeRes.headers.get('content-type') || ''
      const awayType = awayRes.headers.get('content-type') || ''
      if (!homeType.includes('application/json') || !awayType.includes('application/json')) {
        throw new Error('Backend returned HTML instead of JSON for team stats')
      }

      const [homeData, awayData] = await Promise.all([
        homeRes.json(),
        awayRes.json()
      ])

      setTeamStats({ home: homeData, away: awayData })
    } catch (e) {
      console.error('Failed to load team stats', e)
      setStatsError(e?.message || 'Failed to load team stats')
      setTeamStats(null)
    }
    setStatsLoading(false)
  }

  function closeModal() {
    setSelectedMatch(null)
    setTeamStats(null)
    setStatsError(null)
    setStatsLoading(false)
  }

  return (
    <div className="app-layout">
      <div className="header">
        <div className="eyebrow">World Cup 2026</div>
        <h1>Data Explorer</h1>
        <p className="subtitle">Ask about matches, players, teams, and stats</p>
      </div>

      <div style={{ display: "flex", gap: 8, padding: "0 24px", marginBottom: 8 }}>
        {['home', 'explorer', 'finder', 'leaderboards', 'bracket'].map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className="nav-tab-button"
            style={{
              padding: "10px 22px", borderRadius: 8, border: "none",
              cursor: "pointer", fontSize: 16, fontWeight: 600,
              background: activeTab === tab ? "#1a1a2e" : "#f0f0f0",
              color: activeTab === tab ? "#fff" : "#333"
            }}>
            {{
              home: 'Home',
              explorer: 'Data Explorer',
              finder: 'Player Finder',
              leaderboards: 'Leaderboards',
              bracket: 'Knockout Bracket',
            }[tab]}
          </button>
        ))}
      </div>

      {apiError && <div className="error-banner" style={{ maxWidth: 'calc(100% - 48px)' }}>{apiError}</div>}

      {activeTab === 'home' && <LandingPage onNavigate={setActiveTab} />}

      {activeTab === 'finder' && <PlayerFinder />}

      {activeTab === 'explorer' && (
        <div className="tab-fade-in">
          <SearchPanel
            question={question}
            setQuestion={setQuestion}
            queryMode={queryMode}
            setQueryMode={setQueryMode}
            loading={loading}
            onSubmit={handleSubmit}
          />

          {error && <div className="error-banner">{error}</div>}

          <div className="main-layout">
            <div className="results-panel">
              <ResultPanel
                loading={loading}
                loadingElapsed={loadingElapsed}
                result={result}
                answeredQuestion={answeredQuestion}
                showSql={showSql}
                setShowSql={setShowSql}
              />
            </div>

            <MatchSidebar upcoming={upcoming} flashingMatches={flashingMatches} onMatchClick={handleMatchClick} />

            <MatchModal
              match={selectedMatch}
              teamStats={teamStats}
              statsLoading={statsLoading}
              statsError={statsError}
              onClose={closeModal}
            />
          </div>
        </div>
      )}

      <LeaderboardsTab active={activeTab === 'leaderboards'} />

      {activeTab === 'bracket' && (
        <div className="tab-fade-in" style={{ padding: "0 24px" }}>
          <Bracket />
        </div>
      )}
    </div>
  )
}
