# FIFA World Cup 2026 Data Explorer

Natural language query app — user types English questions, gets SQL-powered answers with charts.

## Stack
- Backend: Python, FastAPI, SQLite, Groq (llama-3.3-70b-versatile)
- Frontend: React + Plotly.js
- Data: Zafronix API, Flashscore via sportdb.dev, ESPN (live scores)

## Project structure
```
backend/
  agent.py          # main pipeline
  llm.py            # all LLM calls
  prompts.py        # all system prompts
  db.py             # SQLite connections
  sync.py           # Zafronix → worldcup.db
  sync3.py          # Flashscore → worldcup_stats.db
  update_recent.py  # incremental daily sync
  logger.py         # structured logging
  main.py           # FastAPI server

frontend/src/
  App.jsx           # main UI
  Bracket.jsx       # knockout bracket
```

## Databases
- worldcup.db — teams, matches, standings, goals, cards, lineups, substitutions, match_stats
- worldcup_stats.db — Flashscore player stats: players, match_player_stats, match_stat_values, goalkeeper_match_stats, tournament_player_stats, tournament_stat_values, awards, stat_types

## Agent pipeline
1. validate_and_route() — validates + routes (use_primary/use_stats) + rewrites question
2. _retrieve() — generates SQL, executes, retries on error
3. combine_results() — merges both sources if both used
4. verify_result() — checks results, retries if wrong
5. generate_viz() — decides chart type or null
6. log_pipeline() — structured JSON log

## Prompts
- VALIDATE_PROMPT: validate + route + rewrite in one call
- PRIMARY_SQL_PROMPT: worldcup.db queries (attaches worldcup_stats.db as schema "stats")
- STATS_SQL_PROMPT: worldcup_stats.db queries
- COMBINE_PROMPT: merges primary + stats results
- VERIFY_PROMPT: validates results
- VIZ_PROMPT: decides visualization

## API endpoints
- POST /query → {sql, rows, viz, error}
- GET /today-matches → ESPN live scores
- GET /bracket → knockout bracket
- GET /team-stats/{team_name} → team stats for modal
- GET /health

## Frontend
- Tab 1: Data Explorer — search → table + Plotly chart + collapsible SQL
- Tab 2: Knockout Bracket
- Sidebar: live/upcoming matches, polling every 15s
- Modal: team comparison on match click

## Environment (.env)
- GROQ_API_KEY
- ZAFRONIX_KEY
- FOOTBALLDATA_KEY
- SPORTDB_KEY

## Run
```bash
# backend
cd backend && uvicorn main:app --reload

# frontend
cd frontend && npm run dev

# manual sync
python sync.py          # full sync (run once)
python update_recent.py # daily incremental
python sync3.py         # player stats sync

# tests
python tests/test_agent.py
```

## Current priorities
- Remove worldcup_fd.db references completely
- Player stat radar chart visualizations
- Conversation context for follow-up queries
- Query caching for repeated questions