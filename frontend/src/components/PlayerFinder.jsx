import { useState, useEffect } from 'react'

const OPERATORS = [
  ['gte', '≥'],
  ['gt', '>'],
  ['lte', '≤'],
  ['lt', '<'],
  ['eq', '='],
]

function emptyFilter() {
  return { stat_key: '', operator: 'gte', value: '' }
}

export default function PlayerFinder() {
  const [statOptions, setStatOptions] = useState(null)
  const [optionsError, setOptionsError] = useState(null)
  const [filters, setFilters] = useState([emptyFilter()])
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/player-finder/options')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then(data => setStatOptions(data.stats || []))
      .catch(e => setOptionsError(e?.message || 'Failed to load filter options.'))
  }, [])

  const statsByCategory = (statOptions || []).reduce((acc, s) => {
    ;(acc[s.category] ||= []).push(s)
    return acc
  }, {})

  function updateFilter(index, field, value) {
    setFilters(prev => prev.map((f, i) => (i === index ? { ...f, [field]: value } : f)))
  }

  function addFilter() {
    if (filters.length >= 5) return
    setFilters(prev => [...prev, emptyFilter()])
  }

  function removeFilter(index) {
    setFilters(prev => prev.filter((_, i) => i !== index))
  }

  async function handleSearch() {
    const valid = filters.filter(f => f.stat_key && f.value !== '')
    if (!valid.length) {
      setError('Add at least one filter with a stat and value.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/player-finder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filters: valid }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setResults(data)
    } catch (e) {
      setError(e?.message || 'Failed to run search.')
      setResults(null)
    }
    setLoading(false)
  }

  return (
    <div className="tab-fade-in" style={{ padding: '0 24px 24px' }}>
      <div className="finder-panel">
        <div className="finder-header">
          <div className="answer-kicker">Player Finder</div>
          <h2 style={{ margin: '4px 0 0' }}>Filter players by stat thresholds</h2>
        </div>

        {optionsError && <div className="error-banner">{optionsError}</div>}

        <div className="finder-filters">
          {filters.map((f, i) => (
            <div className="finder-filter-row" key={i}>
              <select
                className="finder-select"
                value={f.stat_key}
                onChange={e => updateFilter(i, 'stat_key', e.target.value)}
              >
                <option value="">Select a stat…</option>
                {Object.entries(statsByCategory).map(([category, stats]) => (
                  <optgroup key={category} label={category}>
                    {stats.map(s => (
                      <option key={s.stat_key} value={s.stat_key}>{s.label}</option>
                    ))}
                  </optgroup>
                ))}
              </select>

              <select
                className="finder-select finder-select-op"
                value={f.operator}
                onChange={e => updateFilter(i, 'operator', e.target.value)}
              >
                {OPERATORS.map(([op, symbol]) => (
                  <option key={op} value={op}>{symbol}</option>
                ))}
              </select>

              <input
                className="finder-value-input"
                type="number"
                step="any"
                placeholder="value"
                value={f.value}
                onChange={e => updateFilter(i, 'value', e.target.value)}
              />

              {filters.length > 1 && (
                <button className="finder-remove-btn" onClick={() => removeFilter(i)} aria-label="Remove filter">✕</button>
              )}
            </div>
          ))}
        </div>

        <div className="finder-actions">
          <button className="finder-add-btn" onClick={addFilter} disabled={filters.length >= 5}>
            + Add filter
          </button>
          <button className="finder-search-btn" onClick={handleSearch} disabled={loading}>
            {loading && <span className="button-spinner" aria-hidden="true" />}
            {loading ? 'Searching…' : 'Find Players'}
          </button>
        </div>

        {error && <div className="error-banner" style={{ margin: '16px 0 0' }}>{error}</div>}
      </div>

      {results && (
        <div className="result-shell" style={{ marginTop: 20 }}>
          <div className="answer-header">
            <div>
              <div className="answer-kicker">Results</div>
              <h2>{results.rows.length} player{results.rows.length === 1 ? '' : 's'} matched</h2>
            </div>
          </div>

          {results.rows.length === 0 ? (
            <div className="answer-empty">
              <strong>No players matched these filters.</strong>
              <span>Try loosening a threshold or removing a filter.</span>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Team</th>
                    <th>Position</th>
                    <th>Matches</th>
                    <th>Avg Rating</th>
                    {results.filters.map((f, i) => <th key={i}>{f.label}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {results.rows.map((row, i) => (
                    <tr key={i}>
                      <td>{row.name || '—'}</td>
                      <td>{row.team || '—'}</td>
                      <td>{row.position || '—'}</td>
                      <td>{row.matches_played ?? '—'}</td>
                      <td>{row.avg_rating ?? '—'}</td>
                      {results.filters.map((f, fi) => (
                        <td key={fi}>{row[`filter_${fi}`] ?? '—'}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
