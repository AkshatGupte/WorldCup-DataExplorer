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

export default function LandingPage({ onNavigate }) {
  return (
    <div className="tab-fade-in" style={{ padding: '0 24px 32px' }}>
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
