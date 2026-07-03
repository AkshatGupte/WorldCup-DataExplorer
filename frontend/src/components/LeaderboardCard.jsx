import LeaderboardRow from './LeaderboardRow'

// Ranked magnitude list — one sequential hue (gold), bar length is the only
// encoding, value labeled at the tip. No legend: a single series names itself
// via the card title. Built in plain HTML rather than a chart library since a
// compact rank + name + inline-bar + value row isn't a native chart layout.
export default function LeaderboardCard({ title, items, valueFormatter, subtitleKey = 'team' }) {
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
