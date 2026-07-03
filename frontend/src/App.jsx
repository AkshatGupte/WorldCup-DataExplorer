import { useMemo, useState, useEffect, useRef } from 'react'
import Plot from 'react-plotly.js'
import Bracket from './Bracket'

// Per-match ceilings used to normalize each radar axis onto a comparable 0-100 scale.
// Raw stat_key values mix wildly different units (e.g. duelsWon ~0-3 per match vs
// passesAccuracy stored as a 0-1 fraction) — plotting them on one shared linear axis
// makes every small-scale stat collapse invisibly near the center. Calibrated from
// actual match_stat_values ranges in worldcup_stats.db, tuned so a genuinely great
// single-match performance reads as ~90-100%, not maxed out or invisible.
const STAT_SCALE_MAX = {
  goals: 3, assistsGoal: 2, expectedGoals: 1.5, expectedGoalsOnTarget: 1.2, expectedAssists: 1,
  shotsTotal: 6, shotsOnTarget: 4, shotsOffTarget: 4, shotsBlocked: 3, shotsBoxIn: 4, shotsBoxOut: 3, shotsHead: 2,
  bigChancesCreated: 4, bigChancesMissed: 3, keyPasses: 5, offsides: 3,
  touchesBoxOpposite: 15, touchesTotal: 120,
  dribblesTotal: 8, dribblesWon: 5,
  passesTotal: 120, passesAccurate: 100,
  passesFinalThirdTotal: 20, passesFinalThirdAccurate: 15,
  longBallsTotal: 15, longBallsAccurate: 8,
  crossesTotal: 10, crossesAccurate: 4,
  tacklesTotal: 6, tacklesWon: 5,
  interceptions: 4, clearances: 10,
  duelsTotal: 15, duelsWon: 10, duelsGroundTotal: 12, duelsGroundWon: 8, duelsAerialTotal: 8, duelsAerialWon: 6,
  cardsYellow: 1, cardsRed: 1, foulsCommitted: 4, foulsSuffered: 4,
  errorsLeadToGoal: 1, errorsLeadToShot: 2, goalsOwn: 1,
  savesTotal: 8, goalsConceded: 4, goalsPrevented: 3, expectedGoalsOnTargetFaced: 4,
  keeperSweeperTotal: 4, keeperThrowsTotal: 10, punchesTotal: 3,
  fsRating: 10, matchMinutesPlayed: 120,
}
// *Accuracy/*Efficiency stat_keys are stored as 0-1 fractions in the DB (confirmed against
// live data — passesAccuracy ranges 0-1, not 0-100), so their ceiling is always 1.
for (const key of ['passesAccuracy', 'dribblesEfficiency', 'tacklesEfficiency', 'duelsEfficiency',
  'duelsGroundEfficiency', 'duelsAerialEfficiency', 'longBallsAccuracy', 'crossesAccuracy', 'passesFinalThirdAccuracy']) {
  STAT_SCALE_MAX[key] = 1
}

// Sum for cumulative counting stats across matches; average for rates/percentages/ratings —
// summing an accuracy percentage across 3 matches would be meaningless.
function isRateStat(label) {
  return /Accuracy|Efficiency/i.test(label) || label === 'fsRating'
}

// Animates a number counting up from 0 to `target` — used on leaderboard values so
// they feel alive on first render instead of just appearing as static text.
function useCountUp(target, duration = 900) {
  const [value, setValue] = useState(0)
  useEffect(() => {
    let raf
    const start = performance.now()
    const from = 0
    const tick = now => {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3) // ease-out cubic
      setValue(from + (target - from) * eased)
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, duration])
  return value
}

// One leaderboard row as a real component (not a plain function called in a loop) —
// useCountUp is a hook, and hooks can only run inside an actual component instance,
// not inside a .map() callback in a shared parent's render. Bar fill and the number
// both animate in together, staggered per rank for a cascading reveal.
function LeaderboardRow({ rank, item, maxValue, subtitleKey, valueFormatter }) {
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

export default function App() {
  const [question, setQuestion] = useState('')
  const [answeredQuestion, setAnsweredQuestion] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [apiError, setApiError] = useState(null)
  const [upcoming, setUpcoming] = useState(null)
  const [flashingMatches, setFlashingMatches] = useState({})
  const previousScores = useRef({})
  const [selectedMatch, setSelectedMatch] = useState(null)
  const [teamStats, setTeamStats] = useState(null)
  const [statsLoading, setStatsLoading] = useState(false)
  const [statsError, setStatsError] = useState(null)
  const [activeTab, setActiveTab] = useState('explorer')
  const [showSql, setShowSql] = useState(false)
  const [queryMode, setQueryMode] = useState('general')
  const [leaderboards, setLeaderboards] = useState(null)
  const [leaderboardsLoading, setLeaderboardsLoading] = useState(false)
  const [leaderboardsError, setLeaderboardsError] = useState(null)

  useEffect(() => {
    loadUpcoming()
    const interval = setInterval(loadUpcoming, 15000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (activeTab === 'leaderboards' && !leaderboards && !leaderboardsLoading) {
      loadLeaderboards()
    }
  }, [activeTab])

  async function loadLeaderboards() {
    setLeaderboardsLoading(true)
    setLeaderboardsError(null)
    try {
      const res = await fetch('/leaderboards')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setLeaderboards(data)
    } catch (e) {
      setLeaderboardsError(e?.message || 'Failed to load leaderboards.')
    }
    setLeaderboardsLoading(false)
  }

  async function handleSubmit() {
    if (!question.trim()) return
    setLoading(true)
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
      setApiError('Backend is not running. Start the API on port 8000 to use queries and matches.')
    }
    setLoading(false)
  }

  
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
      setApiError('Backend is not running. Start the API on port 8000 to load matches and live data.')
      setUpcoming([])
    }
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
  const cols = useMemo(() => {
    return result?.rows?.length ? Object.keys(result.rows[0]) : []
  }, [result])

  const resultRows = Array.isArray(result?.rows) ? result.rows : []
  const resultError = result?.error || null
  const resultViz = result?.viz || null

  const liveMatches = useMemo(() => {
    return (upcoming || []).filter(match => match.is_live)
  }, [upcoming])

  const finishedMatches = useMemo(() => {
    return (upcoming || []).filter(match => !match.is_live && match.state === 'post')
  }, [upcoming])

  const scheduledMatches = useMemo(() => {
    return (upcoming || []).filter(match => !match.is_live && match.state === 'pre')
  }, [upcoming])

  function formatCell(value) {
    if (value === null || value === undefined) return '—'
    if (typeof value === 'object') return JSON.stringify(value, null, 2)
    return String(value)
  }

  function formatLabel(key) {
    return key
      .replace(/_/g, ' ')
      .replace(/\b\w/g, letter => letter.toUpperCase())
  }

  const CHART_ACCENT = '#f2c300'
  const CHART_ACCENT_2 = '#e31b23'
  const CHART_TEXT = '#f7f5ee'
  const CHART_MUTED = '#b6b0a0'
  const CHART_GRID = 'rgba(247, 245, 238, 0.14)'
  const RADAR_MAX_AXES = 8

  const baseChartLayout = {
    autosize: true,
    margin: { t: 40, b: 60, l: 50, r: 20 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { color: CHART_TEXT, size: 14 }
  }

  // labels: shared axis order (stat_key strings). series: [{ name, values, color }] —
  // values aligned 1:1 with labels. One series = single-player radar; two = overlaid
  // head-to-head comparison on the exact same axes.
  function renderRadarChart(labels, series, title, key) {
    const theta = labels.map(formatLabel)

    // normalize onto a shared 0-100 scale using the curated per-stat ceiling, but never
    // clip — if any series' real value exceeds the assumed ceiling (e.g. summed across
    // several matches instead of one), the axis expands to fit both series rather than
    // flattening the peak or making one player's shape look artificially small
    const ceilings = labels.map((label, i) => {
      const curated = STAT_SCALE_MAX[label]
      const maxRaw = Math.max(...series.map(s => s.values[i] || 0))
      return curated ? Math.max(curated, maxRaw) : (maxRaw > 0 ? maxRaw * 1.15 : 1)
    })

    const data = series.map(s => {
      const normalized = s.values.map((v, i) => Math.max(0, (v / ceilings[i]) * 100))
      const rawText = labels.map((label, i) => {
        const v = s.values[i]
        const display = isRateStat(label) ? `${(v * 100).toFixed(0)}%` : (Number.isInteger(v) ? v : v.toFixed(2))
        return series.length > 1 ? `${s.name} — ${formatLabel(label)}: ${display}` : `${formatLabel(label)}: ${display}`
      })
      return {
        type: "scatterpolar",
        r: [...normalized, normalized[0]],
        theta: [...theta, theta[0]],
        text: [...rawText, rawText[0]],
        hovertemplate: '%{text}<extra></extra>',
        fill: "toself",
        fillcolor: s.color === CHART_ACCENT ? 'rgba(242, 195, 0, 0.25)' : 'rgba(227, 27, 35, 0.25)',
        line: { color: s.color, width: 2 },
        marker: { color: s.color, size: 6 },
        name: s.name
      }
    })

    const layout = {
      ...baseChartLayout,
      title: { text: title, font: { color: CHART_TEXT, size: 18 } },
      margin: { t: 55, b: series.length > 1 ? 76 : 44, l: 44, r: 44 },
      polar: {
        bgcolor: 'transparent',
        radialaxis: {
          visible: true, range: [0, 100], showticklabels: false,
          gridcolor: CHART_GRID, linecolor: CHART_GRID
        },
        angularaxis: { gridcolor: CHART_GRID, linecolor: CHART_GRID, tickfont: { color: CHART_TEXT, size: 14 } }
      },
      showlegend: series.length > 1,
      legend: { font: { color: CHART_TEXT, size: 14 }, orientation: 'h', x: 0.5, xanchor: 'center', y: -0.1 }
    }
    return <Plot key={key} data={data} layout={layout} style={{ width: '100%', minWidth: 0, flex: '1 1 320px' }} useResizeHandler />
  }

  function renderChart(rows, viz) {
    if (!viz || !rows.length) return null

    if (viz.type === "radar") {
      // group by series (player) if present, then by stat label within each series —
      // a "detailed stats" query returns one row per match, so multiple matches share
      // the same stat_key and need aggregating rather than dropping repeats.
      const seriesGroups = new Map()   // seriesName -> Map(label -> raw values[])
      const labelOrder = []
      const labelSeen = new Set()
      for (const row of rows) {
        const label = row[viz.x]
        const value = row[viz.y]
        if (label == null || value == null) continue
        const seriesName = viz.series ? (row[viz.series] ?? 'Unknown') : 'Stats'
        if (!seriesGroups.has(seriesName)) seriesGroups.set(seriesName, new Map())
        const labelMap = seriesGroups.get(seriesName)
        if (!labelMap.has(label)) labelMap.set(label, [])
        labelMap.get(label).push(value)
        if (!labelSeen.has(label)) { labelSeen.add(label); labelOrder.push(label) }
      }
      if (!labelOrder.length || !seriesGroups.size) return null

      // sum counting stats across matches; average rate/accuracy/rating stats, since
      // summing a percentage across matches would be meaningless
      let labels = labelOrder
      let series = [...seriesGroups.entries()].map(([name, labelMap]) => ({
        name,
        values: labels.map(label => {
          const vals = labelMap.get(label)
          if (!vals || !vals.length) return 0
          return isRateStat(label) ? vals.reduce((a, b) => a + b, 0) / vals.length : vals.reduce((a, b) => a + b, 0)
        })
      }))

      // too many raw features (e.g. a "detailed stats" dump with 50+ stat keys) —
      // prefer axes any series has non-zero, then cap so each chart stays legible
      const RADAR_MAX_TOTAL = RADAR_MAX_AXES * 2
      if (labels.length > RADAR_MAX_TOTAL) {
        const nonZeroIdx = labels.map((_, i) => i).filter(i => series.some(s => s.values[i] !== 0))
        const keepIdx = (nonZeroIdx.length >= 4 ? nonZeroIdx : labels.map((_, i) => i)).slice(0, RADAR_MAX_TOTAL)
        labels = keepIdx.map(i => labels[i])
        series = series.map(s => ({ ...s, values: keepIdx.map(i => s.values[i]) }))
      }

      const colors = [CHART_ACCENT, CHART_ACCENT_2]
      series = series.map((s, i) => ({ ...s, color: colors[i % colors.length] }))
      const title = viz.title || (viz.series ? 'Player Comparison' : 'Stats')

      // too many axes on one radar is illegible — split into two side by side,
      // keeping both players' traces together on each half so they stay comparable
      if (labels.length > RADAR_MAX_AXES) {
        const mid = Math.ceil(labels.length / 2)
        const labels1 = labels.slice(0, mid), labels2 = labels.slice(mid)
        const series1 = series.map(s => ({ ...s, values: s.values.slice(0, mid) }))
        const series2 = series.map(s => ({ ...s, values: s.values.slice(mid) }))
        return (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, width: '100%', marginBottom: 24 }}>
            {renderRadarChart(labels1, series1, `${title} (1/2)`, 'radar-1')}
            {renderRadarChart(labels2, series2, `${title} (2/2)`, 'radar-2')}
          </div>
        )
      }

      return <div style={{ width: '100%', marginBottom: 24 }}>{renderRadarChart(labels, series, title, 'radar-single')}</div>
    }

    const x = rows.map(r => r[viz.x])
    const y = rows.map(r => r[viz.y])
    let data = []
    const layout = { ...baseChartLayout, title: { text: viz.title, font: { color: CHART_TEXT, size: 18 } } }

    if (viz.type === "bar") {
      data = [{ type: "bar", x, y, marker: { color: CHART_ACCENT } }]
    } else if (viz.type === "pie") {
      data = [{ type: "pie", labels: x, values: y, marker: { colors: [CHART_ACCENT, CHART_ACCENT_2, CHART_MUTED, '#5a5548', '#8a8470'] } }]
    } else if (viz.type === "scatter") {
      data = [{ type: "scatter", mode: "markers", x, y, marker: { color: CHART_ACCENT, size: 9 } }]
    } else if (viz.type === "line") {
      data = [{ type: "scatter", mode: "lines+markers", x, y, line: { color: CHART_ACCENT }, marker: { color: CHART_ACCENT } }]
    } else {
      return null
    }

    return <Plot data={data} layout={layout} style={{ width: '100%', marginBottom: 24 }} useResizeHandler />
  }

  // Ranked magnitude list — one sequential hue (gold), bar length is the only
  // encoding, value labeled at the tip. No legend: a single series names itself
  // via the card title. Built in plain HTML rather than Plotly since a compact
  // rank + name + inline-bar + value row isn't a native chart layout.
  function renderLeaderboardCard(title, items, valueFormatter, subtitleKey = 'team') {
    if (!items || !items.length) return null
    const maxValue = Math.max(...items.map(i => i.value), 0.0001)
    return (
      <div className="leaderboard-card">
        <div className="leaderboard-card-title">{title}</div>
        <div className="leaderboard-rows">
          {items.map((item, i) => (
            <LeaderboardRow
              key={i}
              rank={i + 1}
              item={item}
              maxValue={maxValue}
              subtitleKey={subtitleKey}
              valueFormatter={valueFormatter}
            />
          ))}
        </div>
      </div>
    )
  }

  function getResultMeta(rows) {
    if (!rows?.length) return 'No matching records'
    const rowCount = rows.length
    return `${rowCount.toLocaleString()} result${rowCount === 1 ? '' : 's'} found`
  }

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

  function getLiveCardText(match) {
    const status = `${match?.short_detail || ''} ${match?.status || ''}`.toLowerCase()
    if (status.includes('half time') || status.includes('halftime') || status.includes('ht')) return 'Half Time'
    return match?.clock || match?.short_detail || 'LIVE'
  }

  function renderLoadingSkeleton() {
    return (
      <div className="result-shell">
        <div className="answer-header">
          <div>
            <div className="answer-kicker">Answer</div>
            <div className="skeleton-line skeleton-title" />
          </div>
          <div className="skeleton-pill" />
        </div>

        <div className="answer-summary">
          <div className="skeleton-line" />
          <div className="skeleton-line skeleton-line-short" />
        </div>

        <div className="chart-panel">
          <div className="skeleton-bars">
            <div className="skeleton-bar" />
            <div className="skeleton-bar" />
            <div className="skeleton-bar" />
          </div>
        </div>

        <div className="data-section">
          <div className="data-section-header">
            <div>
              <div className="answer-kicker">Supporting Data</div>
              <div className="skeleton-line skeleton-section-title" />
            </div>
            <div className="skeleton-pill skeleton-pill-small" />
          </div>
          <div className="table-wrap skeleton-table">
            <div className="skeleton-table-row skeleton-table-head" />
            <div className="skeleton-table-row" />
            <div className="skeleton-table-row" />
            <div className="skeleton-table-row" />
          </div>
        </div>
      </div>
    )
  }

  function renderLeaderboardsSkeleton() {
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

return (
    <div className="app-layout">
      <div className="header">
        <div className="eyebrow">World Cup 2026</div>
        <h1>Data Explorer</h1>
        <p className="subtitle">Ask about matches, players, teams, and stats</p>
      </div>

      <div style={{ display: "flex", gap: 8, padding: "0 24px", marginBottom: 8 }}>
        {['explorer', 'leaderboards', 'bracket'].map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className="nav-tab-button"
            style={{
              padding: "10px 22px", borderRadius: 8, border: "none",
              cursor: "pointer", fontSize: 16, fontWeight: 600,
              background: activeTab === tab ? "#1a1a2e" : "#f0f0f0",
              color: activeTab === tab ? "#fff" : "#333"
            }}>
            {tab === 'explorer' ? 'Data Explorer' : tab === 'leaderboards' ? 'Leaderboards' : 'Knockout Bracket'}
          </button>
        ))}
      </div>

      {apiError && <div className="error-banner" style={{ maxWidth: 'calc(100% - 48px)' }}>{apiError}</div>}

      {activeTab === 'explorer' && <div className="tab-fade-in">
        <div className="search-section">
          <div className="mode-toggle">
            {[['general', 'General'], ['player', 'Player Stats']].map(([m, label]) => (
              <button
                key={m}
                className={`mode-pill${queryMode === m ? ' active' : ''}`}
                onClick={() => setQueryMode(m)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="search-box">
            <input
              value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSubmit()}
              placeholder={queryMode === 'player'
                ? "Ask about a player's ratings, stats, or performance..."
                : "Ask about teams, players, or matches..."}
            />
            <button onClick={handleSubmit} disabled={loading}>
              {loading && <span className="button-spinner" aria-hidden="true" />}
              {loading ? 'Searching…' : 'Search'}
            </button>
          </div>
          <p className="search-hint">
            {queryMode === 'player'
              ? 'Player Stats mode — ratings, xG, passing, defensive stats. Use full names like "Lionel Messi".'
              : 'General mode — teams, fixtures, standings, match events. Use full names like "Lionel Messi" or "Brazil".'}
          </p>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <div className="main-layout">
          <div className="results-panel">
            {loading ? renderLoadingSkeleton() : result ? (
              <div className="result-shell">
                <div className="answer-header">
                  <div>
                    <div className="answer-kicker">Answer</div>
                    <h2>{answeredQuestion || 'World Cup result'}</h2>
                  </div>
                  <span className="answer-meta">{getResultMeta(resultRows)}</span>
                </div>

                {result.sql && (result.sql.primary || result.sql.secondary) && (
                  <div className="sql-panel">
                    <button className="sql-toggle" onClick={() => setShowSql(v => !v)}>
                      <span className={`sql-toggle-arrow${showSql ? ' open' : ''}`}>▸</span> {showSql ? 'Hide' : 'Show'} SQL
                    </button>
                    {showSql && (
                      <div className="sql-content tab-fade-in">
                        {result.sql.primary && (
                          <>
                            <div className="sql-label">Primary</div>
                            <pre className="sql-block">{result.sql.primary}</pre>
                          </>
                        )}
                        {result.sql.secondary && (
                          <>
                            <div className="sql-label">Stats</div>
                            <pre className="sql-block">{result.sql.secondary}</pre>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {resultError ? (
                  <div className="answer-empty">{resultError}</div>
                ) : resultRows.length === 0 ? (
                  <div className="answer-empty">
                    <strong>No results found.</strong>
                    <span>Try asking with a team, player, match, or competition stage name.</span>
                  </div>
                ) : (
                  <>
                    <div className="answer-summary">
                      {result.summary || 'Here are the matching World Cup records.'}
                    </div>

                    {resultViz && (
                      <div className="chart-panel">
                        {renderChart(resultRows, resultViz)}
                      </div>
                    )}

                    <div className="data-section">
                      <div className="data-section-header">
                        <div>
                          <div className="answer-kicker">Supporting Data</div>
                          <h3>Full Results</h3>
                        </div>
                        <span className="muted">{cols.length} field{cols.length === 1 ? '' : 's'}</span>
                      </div>
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              {cols.map(c => <th key={c}>{formatLabel(c)}</th>)}
                            </tr>
                          </thead>
                          <tbody>
                            {resultRows.map((row, i) => (
                              <tr key={i}>
                                {cols.map(c => (
                                  <td key={c}>
                                    {typeof row[c] === 'object' ? <pre className="cell-json">{formatCell(row[c])}</pre> : formatCell(row[c])}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div className="placeholder">
                <div style={{ fontSize: 48, marginBottom: 16 }}>⚽</div>
                <p style={{ color: '#999', marginBottom: 0 }}>Search for World Cup data to get started</p>
              </div>
            )}
          </div>

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
                        <div key={`live-${i}`} className="match-card live" onClick={() => handleMatchClick(m)} style={{ cursor: 'pointer' }}>
                          <div className="match-topline">
                            <div className="match-status live-badge live-clock">{getLiveCardText(m)}</div>
                          </div>
                          <div className="match-team">
                            {m.home.logo && <img src={m.home.logo} alt={m.home.name} className="team-logo" />}
                            <span>{m.home.name}</span>
                          </div>
                          <div className={`scoreline${flashingMatches[`${m.home?.name}-${m.away?.name}`] ? ' score-flash' : ''}`}>
                            {m.home_score ?? '0'} - {m.away_score ?? '0'}
                          </div>
                          <div className="match-team">
                            {m.away.logo && <img src={m.away.logo} alt={m.away.name} className="team-logo" />}
                            <span>{m.away.name}</span>
                          </div>
                          <div className="match-details">
                            {m.venue && <div className="match-venue">{m.venue}</div>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {finishedMatches.length > 0 && (
                  <div className="match-group">
                    <div className="match-group-title">Finished Today</div>
                    <div className="matches-list">
                      {finishedMatches.map((m, i) => (
                        <div key={`finished-${i}`} className="match-card" onClick={() => handleMatchClick(m)} style={{ cursor: 'pointer' }}>
                          <div className="match-topline">
                            <div className="match-status">FULL TIME</div>
                          </div>
                          <div className="match-team">
                            {m.home.logo && <img src={m.home.logo} alt={m.home.name} className="team-logo" />}
                            <span>{m.home.name}</span>
                          </div>
                          <div className="scoreline">{m.home_score ?? '0'} - {m.away_score ?? '0'}</div>
                          <div className="match-team">
                            {m.away.logo && <img src={m.away.logo} alt={m.away.name} className="team-logo" />}
                            <span>{m.away.name}</span>
                          </div>
                          <div className="match-details">
                            {m.venue && <div className="match-venue">{m.venue}</div>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {scheduledMatches.length > 0 && (
                  <div className="match-group">
                    <div className="match-group-title">Upcoming Fixtures</div>
                    <div className="matches-list">
                      {scheduledMatches.map((m, i) => (
                        <div key={`upcoming-${i}`} className="match-card" onClick={() => handleMatchClick(m)} style={{ cursor: 'pointer' }}>
                          <div className="match-status">{m.status}</div>
                          <div className="match-team">
                            {m.home.logo && <img src={m.home.logo} alt={m.home.name} className="team-logo" />}
                            <span>{m.home.name}</span>
                          </div>
                          <div className="match-vs">vs</div>
                          <div className="match-team">
                            {m.away.logo && <img src={m.away.logo} alt={m.away.name} className="team-logo" />}
                            <span>{m.away.name}</span>
                          </div>
                          <div className="match-details">
                            <div className="match-time">{m.date ? new Date(m.date).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'TBD'}</div>
                            {m.venue && <div className="match-venue">{m.venue}</div>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <p className="muted">Loading…</p>
            )}
          </div>

          {selectedMatch && (
            <div className="modal-overlay" onClick={() => { setSelectedMatch(null); setTeamStats(null); setStatsError(null); setStatsLoading(false); }}>
              <div className="modal-content" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                  <div className="modal-header-left">
                    <h2>Team Comparison</h2>
                    {getMatchPhase(selectedMatch) && (
                      <div className="match-phase-tag">{getMatchPhase(selectedMatch)}</div>
                    )}
                  </div>
                  <button className="modal-close" onClick={() => { setSelectedMatch(null); setTeamStats(null); setStatsError(null); setStatsLoading(false); }}>✕</button>
                </div>
                <div className="fixture-banner">
                  <div className="fixture-team">
                    {selectedMatch.home.logo && <img src={selectedMatch.home.logo} alt={selectedMatch.home.name} className="fixture-logo" />}
                    <span>{selectedMatch.home.name}</span>
                  </div>
                  <div className="fixture-score">
                    <div className="score-text">
                      {selectedMatch.state === 'pre'
                        ? 'vs'
                        : <>{selectedMatch.home_score ?? 0} <span className="dash">-</span> {selectedMatch.away_score ?? 0}</>}
                    </div>
                    <div className="score-sub">{getCenterText(selectedMatch)}</div>
                  </div>
                  <div className="fixture-team">
                    {selectedMatch.away.logo && <img src={selectedMatch.away.logo} alt={selectedMatch.away.name} className="fixture-logo" />}
                    <span>{selectedMatch.away.name}</span>
                  </div>
                </div>

                <div className="fixture-meta">
                  <div>{selectedMatch.status || 'Upcoming fixture'}</div>
                  {selectedMatch.venue && <div>{selectedMatch.venue}</div>}
                </div>

                {statsLoading && (
                  <div className="modal-loading-skeleton" aria-label="Loading team statistics">
                    <div className="skeleton-line" />
                    <div className="skeleton-line skeleton-line-short" />
                    <div className="skeleton-line" />
                  </div>
                )}
                {statsError && <div className="modal-error">{statsError}</div>}

                {(selectedMatch.is_live || selectedMatch.state === 'post') && Array.isArray(selectedMatch.scorers) && selectedMatch.scorers.length > 0 && (
                  <div className="scorers-panel">
                    <div className="scorers-header">Scorers</div>
                    <div className="scorers-rows">
                      {selectedMatch.scorers.map((s, idx) => (
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
                      {selectedMatch.home.logo && <img src={selectedMatch.home.logo} alt={selectedMatch.home.name} className="modal-logo" />}
                      <h3>{selectedMatch.home.name}</h3>
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
                    {(selectedMatch.is_live || selectedMatch.state === 'post') && selectedMatch.scorers && (
                      <div className="scorers-list">
                        <div className="scorers-title">Scorers</div>
                        {selectedMatch.scorers.filter(s => s.team && s.team.toLowerCase().includes(selectedMatch.home.name.toLowerCase())).map((s, idx) => (
                          <div key={idx} className="scorer-row">{s.player || s.desc} <span className="scorer-minute">{s.minute || ''}</span></div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="vs-divider">VS</div>

                  <div className="team-stats">
                    <div className="team-header">
                      {selectedMatch.away.logo && <img src={selectedMatch.away.logo} alt={selectedMatch.away.name} className="modal-logo" />}
                      <h3>{selectedMatch.away.name}</h3>
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
                    {(selectedMatch.is_live || selectedMatch.state === 'post') && selectedMatch.scorers && (
                      <div className="scorers-list">
                        <div className="scorers-title">Scorers</div>
                        {selectedMatch.scorers.filter(s => s.team && s.team.toLowerCase().includes(selectedMatch.away.name.toLowerCase())).map((s, idx) => (
                          <div key={idx} className="scorer-row">{s.player || s.desc} <span className="scorer-minute">{s.minute || ''}</span></div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>}

      {activeTab === 'leaderboards' && (
        <div className="tab-fade-in" style={{ padding: "0 24px 24px" }}>
          {leaderboardsLoading && renderLeaderboardsSkeleton()}
          {leaderboardsError && <div className="error-banner">{leaderboardsError}</div>}
          {leaderboards && (
            <div className="leaderboard-grid">
              {renderLeaderboardCard('Top 10 Players by xG', leaderboards.top_players_xg, v => v.toFixed(2))}
              {renderLeaderboardCard('Teams by Highest xG', leaderboards.top_teams_xg, v => v.toFixed(2), null)}
              {renderLeaderboardCard('Highest Rated Players', leaderboards.top_rated_players, v => v.toFixed(1))}
              {renderLeaderboardCard('Highest Scoring Teams', leaderboards.top_scoring_teams, v => Math.round(v), null)}
            </div>
          )}
        </div>
      )}

      {activeTab === 'bracket' && (
        <div className="tab-fade-in" style={{ padding: "0 24px" }}>
          <Bracket />
        </div>
      )}

    </div>
  )
}