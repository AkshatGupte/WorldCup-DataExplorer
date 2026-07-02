import { useState, useEffect } from "react"

const STAGE_COLORS = {
  "Round of 32":    "#1a1a2e",
  "Round of 16":    "#16213e",
  "Quarter Finals": "#0f3460",
  "Semi Finals":    "#533483",
  "Third Place":    "#2d6a4f",
  "Final":          "#b5451b",
}

function MatchCard({ match }) {
  const homeWon = match.finished && match.home_score > match.away_score
  const awayWon = match.finished && match.away_score > match.home_score

  return (
    <div style={{
      background: "#1e1e2e",
      border: "1px solid #333",
      borderRadius: 8,
      padding: "10px 14px",
      minWidth: 200,
      fontSize: 15,
    }}>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        marginBottom: 6,
        opacity: awayWon ? 0.45 : 1,
        fontWeight: homeWon ? 700 : 400,
        color: homeWon ? "#fff" : "#aaa"
      }}>
        <span>{match.home}</span>
        <span style={{ marginLeft: 12, color: homeWon ? "#f0c040" : "#ccc" }}>
          {match.home_score ?? "—"}
        </span>
      </div>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        opacity: homeWon ? 0.45 : 1,
        fontWeight: awayWon ? 700 : 400,
        color: awayWon ? "#fff" : "#aaa"
      }}>
        <span>{match.away}</span>
        <span style={{ marginLeft: 12, color: awayWon ? "#f0c040" : "#ccc" }}>
          {match.away_score ?? "—"}
        </span>
      </div>
      {!match.finished && (
        <div style={{ marginTop: 6, fontSize: 13, color: "#666", textAlign: "right" }}>
          upcoming
        </div>
      )}
    </div>
  )
}

function StageColumn({ stage }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, minWidth: 220 }}>
      <div style={{
        fontSize: 13, fontWeight: 700, letterSpacing: 1,
        color: "#888", textTransform: "uppercase", marginBottom: 8,
        padding: "4px 12px", borderRadius: 4,
        background: STAGE_COLORS[stage.name] || "#1a1a2e"
      }}>
        {stage.name}
      </div>
      <div style={{
        display: "flex", flexDirection: "column",
        gap: stage.name === "Round of 32" ? 8 : 24,
        justifyContent: "space-around",
        flex: 1
      }}>
        {stage.matches.map(m => (
          <MatchCard key={m.id} match={m} />
        ))}
      </div>
    </div>
  )
}

export default function Bracket() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    fetch("/bracket")
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  if (error) {
    return (
      <div style={{ padding: "24px 0" }}>
        <h2 style={{ color: "#fff", marginBottom: 24, fontSize: 24 }}>Knockout Bracket</h2>
        <div className="error-banner" style={{ maxWidth: 900, margin: 0 }}>
          Backend is not running or bracket data is unavailable. Start the API on port 8000.
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div style={{ padding: "24px 0" }}>
        <h2 style={{ color: "#fff", marginBottom: 24, fontSize: 24 }}>Knockout Bracket</h2>
        <div className="bracket-loading">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="bracket-skeleton-column">
              <div className="skeleton-bar bracket-skeleton-stage" />
              <div className="skeleton-bar bracket-skeleton-card" />
              <div className="skeleton-bar bracket-skeleton-card" />
              {i === 1 && <div className="skeleton-bar bracket-skeleton-card wide" />}
            </div>
          ))}
        </div>
      </div>
    )
  }
  // separate third place + final from main flow
  const mainStages    = data.stages.filter(s => !["Third Place", "Final"].includes(s.name))
  const specialStages = data.stages.filter(s =>  ["Third Place", "Final"].includes(s.name))

  return (
    <div style={{ padding: "24px 0" }}>
      <h2 style={{ color: "#fff", marginBottom: 24, fontSize: 24 }}>Knockout Bracket</h2>

      {/* main bracket flow */}
      <div style={{
        display: "flex", gap: 24, overflowX: "auto",
        paddingBottom: 16, alignItems: "flex-start"
      }}>
        {mainStages.map(stage => (
          <StageColumn key={stage.key} stage={stage} />
        ))}
      </div>

      {/* third place + final */}
      <div style={{ display: "flex", gap: 24, marginTop: 32, alignItems: "flex-start" }}>
        {specialStages.map(stage => (
          <StageColumn key={stage.key} stage={stage} />
        ))}
      </div>
    </div>
  )
}