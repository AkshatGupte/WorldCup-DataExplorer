import ChartRenderer from './ChartRenderer'
import { formatLabel } from '../chartTheme'

function formatCell(value) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

function getResultMeta(rows) {
  if (!rows?.length) return 'No matching records'
  const rowCount = rows.length
  return `${rowCount.toLocaleString()} result${rowCount === 1 ? '' : 's'} found`
}

function getLoadingMessage(elapsed) {
  if (elapsed < 5) return 'Loading response…'
  if (elapsed < 15) return 'Still working — analyzing your question…'
  if (elapsed < 30) return 'This is taking a little longer than usual…'
  return 'Hang tight — retrying with a backup data provider…'
}

function LoadingSkeleton({ loadingElapsed }) {
  return (
    <div className="result-shell">
      <div className="loading-banner">
        <span className="loading-dot" />
        {getLoadingMessage(loadingElapsed)}
      </div>

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

export default function ResultPanel({ loading, loadingElapsed, result, answeredQuestion, showSql, setShowSql }) {
  if (loading) return <LoadingSkeleton loadingElapsed={loadingElapsed} />

  if (!result) {
    return (
      <div className="placeholder">
        <div style={{ fontSize: 48, marginBottom: 16 }}>⚽</div>
        <p style={{ color: '#999', marginBottom: 0 }}>Search for World Cup data to get started</p>
      </div>
    )
  }

  const resultRows = Array.isArray(result?.rows) ? result.rows : []
  const resultError = result?.error || null
  const resultViz = result?.viz || null
  const cols = resultRows.length ? Object.keys(resultRows[0]) : []

  return (
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
              <ChartRenderer rows={resultRows} viz={resultViz} />
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
  )
}
