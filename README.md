# World Cup 2026 Data Explorer

World Cup 2026 Data Explorer is a full-stack football dashboard for exploring FIFA World Cup data through a conversational interface and live match views.

It combines a React frontend, a FastAPI backend, SQLite data, and external football APIs to present World Cup information in a simple, readable format.

## What it does

- Answers natural-language questions about teams, players, matches, standings, and tournament stats
- Returns results in readable summaries, tables, and charts
- Shows today’s matches and live fixtures in a sidebar
- Opens a match card to compare both teams with wins, goals scored, and top scorers
- Displays the knockout bracket in a separate view
- Uses live football data when available, with fallback messages when the backend is unavailable

## Main features

### Data Explorer
- Ask questions like team comparisons, player stats, match results, and standings
- See a generated response plus supporting records
- View data as a table, summary cards, or a chart

### Match sidebar
- Browse upcoming fixtures
- See ongoing matches with live score and match status
- Open a match to compare both teams

### Match comparison modal
- Displays the fixture prominently
- Shows score and match phase such as live, half time, or full time
- Shows team statistics for both sides

### Knockout bracket
- Displays the tournament knockout stage in bracket form
- Separates later stages such as third place and final

## Project structure

- `backend/` — FastAPI API, SQLite helpers, sync utilities, and query routing
- `frontend/` — React + Vite user interface
- `worldcup.db` — local SQLite database used by the backend

## Tech stack

- Frontend: React, Vite
- Backend: FastAPI, Python
- Storage: SQLite
- Data sources: World Cup APIs and ESPN scoreboard

## Deployment

The backend serves the built frontend itself, so there's a single origin and no
separate frontend host or CORS setup needed for a standard deployment.

1. Build the frontend: `cd frontend && npm install && npm run build` (outputs to `frontend/dist`).
2. Set the backend's environment variables (see `backend/.env`) on your host —
   `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `OPENROUTER_KEY`, `ZAFRONIX_KEY`, `SPORTDB_KEY`, etc.
3. Start the API from the repo root: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   (a `Procfile` with this exact command is included for platforms that use one,
   e.g. Render/Railway).
4. Visiting the deployed URL now serves the React app directly from the API; every
   `/query`, `/leaderboards`, `/bracket`, etc. request is same-origin.

If the frontend is ever hosted separately instead, set `ALLOWED_ORIGINS` (comma-separated)
on the backend to that origin — it defaults to the local Vite dev server only.

Notes:
- SQLite is a local file, so the host needs a persistent disk — this won't work on a
  typical stateless/serverless platform.
- Keep `sync3.py` / `update_recent.py` running on a schedule (cron) so match data and
  stats stay current after the initial sync.

## License

No license has been added yet.