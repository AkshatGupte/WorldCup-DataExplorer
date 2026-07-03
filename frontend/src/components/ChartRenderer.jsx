import Plot from 'react-plotly.js'
import {
  CHART_ACCENT, CHART_ACCENT_2, CHART_TEXT, CHART_MUTED, CHART_GRID,
  RADAR_MAX_AXES, chartConfig, baseChartLayout, STAT_SCALE_MAX, isRateStat, formatLabel
} from '../chartTheme'

// labels: shared axis order (stat_key strings). series: [{ name, values, color }] —
// values aligned 1:1 with labels. One series = single-player radar; two = overlaid
// head-to-head comparison on the exact same axes.
function RadarChart({ labels, series, title, chartKey }) {
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
      mode: "lines+markers",
      r: [...normalized, normalized[0]],
      theta: [...theta, theta[0]],
      text: [...rawText, rawText[0]],
      hovertemplate: '%{text}<extra></extra>',
      hoveron: "points",
      fill: "toself",
      fillcolor: s.color === CHART_ACCENT ? 'rgba(242, 195, 0, 0.25)' : 'rgba(227, 27, 35, 0.25)',
      line: { color: s.color, width: 2 },
      marker: { color: s.color, size: 8 },
      name: s.name
    }
  })

  const layout = {
    ...baseChartLayout,
    title: { text: title, font: { color: CHART_TEXT, size: 18 } },
    margin: { t: 55, b: series.length > 1 ? 76 : 44, l: 44, r: 44 },
    hovermode: "closest",
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
  return <Plot key={chartKey} data={data} layout={layout} config={chartConfig} style={{ width: '100%', minWidth: 0, flex: '1 1 320px' }} useResizeHandler />
}

export default function ChartRenderer({ rows, viz }) {
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
          <RadarChart labels={labels1} series={series1} title={`${title} (1/2)`} chartKey="radar-1" />
          <RadarChart labels={labels2} series={series2} title={`${title} (2/2)`} chartKey="radar-2" />
        </div>
      )
    }

    return <div style={{ width: '100%', marginBottom: 24 }}><RadarChart labels={labels} series={series} title={title} chartKey="radar-single" /></div>
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

  return <Plot data={data} layout={layout} config={chartConfig} style={{ width: '100%', marginBottom: 24 }} useResizeHandler />
}
