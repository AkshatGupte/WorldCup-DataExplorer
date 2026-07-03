// Shared color tokens and chart config used by every chart type and the leaderboard bars.

export const CHART_ACCENT = '#f2c300'
export const CHART_ACCENT_2 = '#e31b23'
export const CHART_TEXT = '#f7f5ee'
export const CHART_MUTED = '#b6b0a0'
export const CHART_GRID = 'rgba(247, 245, 238, 0.14)'
export const RADAR_MAX_AXES = 8

// Hides Plotly's default toolbar (zoom/pan/box-select/lasso-select/download) — several
// of those tools are no-ops on a polar/radar chart and look broken when clicked; none of
// them are needed for a quick chart accompanying a text answer in this app.
export const chartConfig = { displayModeBar: false, responsive: true }

export const baseChartLayout = {
  autosize: true,
  margin: { t: 40, b: 60, l: 50, r: 20 },
  paper_bgcolor: 'transparent',
  plot_bgcolor: 'transparent',
  font: { color: CHART_TEXT, size: 14 }
}

// Per-match ceilings used to normalize each radar axis onto a comparable 0-100 scale.
// Raw stat_key values mix wildly different units (e.g. duelsWon ~0-3 per match vs
// passesAccuracy stored as a 0-1 fraction) — plotting them on one shared linear axis
// makes every small-scale stat collapse invisibly near the center. Calibrated from
// actual match_stat_values ranges in worldcup_stats.db, tuned so a genuinely great
// single-match performance reads as ~90-100%, not maxed out or invisible.
export const STAT_SCALE_MAX = {
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
export function isRateStat(label) {
  return /Accuracy|Efficiency/i.test(label) || label === 'fsRating'
}

export function formatLabel(key) {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, letter => letter.toUpperCase())
}
