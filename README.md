# [World Cup 2026 Data Explorer](https://worldcup-dataexplorer.onrender.com/)

World Cup 2026 Data Explorer is a full-stack football app for exploring FIFA World
Cup 2026 data — ask a question in plain English and get back a real answer, a
chart, or a stat breakdown, alongside live scores, leaderboards, and the
knockout bracket.

## What it does

Type a question like *"How many World Cup goals has Messi scored?"* or *"Compare
Messi and Mbappe's attacking stats"* and the app converts it into a database
query behind the scenes, runs it, and returns a readable answer — with a table,
chart, or radar comparison when one actually helps.

## Features

### Natural-language Data Explorer
- Ask about teams, players, matches, standings, and tournament stats in plain English
- Two search modes: **General** (teams, fixtures, standings, match events) and
  **Player Stats** (ratings, xG, passing, defensive numbers) — biases the
  question toward the right data source while still pulling in the other
  source automatically if a question genuinely needs both
- A collapsible **"Show SQL"** panel reveals the exact query that produced the
  answer, for anyone curious how it works
- Repeat questions answer instantly from cache instead of re-querying

### Player stat radar charts
- Ask for a player's stats and get an automatically-scoped radar chart —
  defenders get defensive numbers, attackers get attacking numbers, midfielders
  get a blended set, so you're never staring at 50 irrelevant stats
- Ask to compare two players and get both overlaid on the same radar, so their
  shapes are directly comparable
- Values are normalized onto a consistent scale so a stat like pass accuracy
  (a percentage) doesn't get dwarfed by a stat like duels won (a raw count)

### Leaderboards
- Top 10 players by expected goals (xG)
- Teams by highest combined xG
- Highest rated players of the tournament
- Highest scoring teams
- Animated, ranked bar lists — numbers count up and bars fill in on load

### Live match sidebar
- Today's matches with live scores, refreshed automatically every 15 seconds
- A pulsing "Live Now" section for matches in progress, with a score flash the
  moment a goal changes the scoreline
- Click any match to open a full comparison

### Match comparison modal
- Shows the fixture, score, and match phase (scheduled, live, half-time, full-time)
- Compares both teams' wins, goals scored, and top scorer
- Lists scorers for finished or in-progress matches

### Knockout bracket
- The full knockout stage in bracket form, from Round of 32 through the Final
- Third place and the Final are shown separately from the main bracket flow

## Project structure

- `backend/` — FastAPI API, SQLite data access, sync utilities, and the natural-language query pipeline
- `frontend/` — React + Vite user interface

## Tech stack

- Frontend: React, Vite, Plotly
- Backend: FastAPI, Python
- Storage: SQLite
- Data sources: Zafronix, Flashscore (via sportdb.dev), ESPN live scores
- LLM: Groq, with Cerebras and OpenRouter as automatic fallbacks

## License

No license has been added yet.
