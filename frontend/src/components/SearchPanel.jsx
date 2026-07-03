export default function SearchPanel({ question, setQuestion, queryMode, setQueryMode, loading, onSubmit }) {
  return (
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
          onKeyDown={e => e.key === 'Enter' && onSubmit()}
          placeholder={queryMode === 'player'
            ? "Ask about a player's ratings, stats, or performance..."
            : "Ask about teams, players, or matches..."}
        />
        <button onClick={onSubmit} disabled={loading}>
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
  )
}
