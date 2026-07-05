from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
import os
import requests
import sqlite3

try:
    from .agent import run
    from .sync import get as external_get
except ImportError:
    from agent import run
    from sync import get as external_get

logging.basicConfig(level=logging.INFO)

DB_PATH = Path(__file__).resolve().parent / "worldcup.db"
STATS_DB_PATH = Path(__file__).resolve().parent / "worldcup_stats.db"
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

app = FastAPI()

# Defaults to the Vite dev server origins for local development. In production,
# the frontend is served from this same FastAPI app (see the StaticFiles mount
# below), so browser requests are same-origin and CORS doesn't even apply — this
# only matters if the frontend is ever hosted on a separate domain, in which case
# set ALLOWED_ORIGINS to a comma-separated list of the real deployed origin(s).
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

app.add_middleware(CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tournament-overview")
def tournament_overview():
    """Headline tournament facts for the home page — deterministic SQL, no LLM."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) AS n FROM teams")
        teams = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM matches")
        matches = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(DISTINCT country) AS n FROM matches")
        host_countries = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(DISTINCT stadium) AS n FROM matches")
        stadiums = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(DISTINCT confederation) AS n FROM teams")
        confederations = cur.fetchone()["n"]
        cur.execute("SELECT MIN(date) AS start, MAX(date) AS end FROM matches")
        dates = cur.fetchone()
        conn.close()

        return {
            "teams": teams,
            "matches": matches,
            "host_countries": host_countries,
            "stadiums": stadiums,
            "confederations": confederations,
            "start_date": dates["start"],
            "end_date": dates["end"],
        }
    except Exception as e:
        logging.exception("Error building tournament overview")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/upcoming")
def upcoming(limit: int = 10):
    try:
        data = external_get("matches", {"year": 2026})
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    matches = data.get("data") if isinstance(data, dict) and data.get("data") is not None else data
    if not isinstance(matches, list):
        raise HTTPException(status_code=502, detail="Unexpected response from external API")

    upcoming_matches = [m for m in matches if m.get("status") in ("scheduled", "live")]
    upcoming_matches.sort(key=lambda m: m.get("kickoffUtc") or m.get("date") or "")
    return upcoming_matches[:limit]


@app.get("/today-matches")
def today_matches():
    try:
        res = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard",
            timeout=10
        )
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        logging.exception("Failed to fetch from ESPN API")
        raise HTTPException(status_code=502, detail=f"ESPN API error: {e}")

    events = data.get("events", [])
    matches = []

    for event in events:
        try:
            comp        = event.get("competitions", [{}])[0]
            competitors = comp.get("competitors", [])
            status      = event.get("status", {}).get("type", {})
            home        = next((c for c in competitors if c.get("homeAway") == "home"), {})
            away        = next((c for c in competitors if c.get("homeAway") == "away"), {})
            state       = status.get("state", "")
            short_detail = status.get("shortDetail", "")

            match = {
                "date":         event.get("date"),
                "status":       status.get("description", ""),
                "state":        state,
                "short_detail": short_detail,
                "clock":        comp.get("status", {}).get("displayClock") or status.get("detail", ""),
                "is_live":      state == "in" or "live" in short_detail.lower(),
                "home_score":   home.get("score"),
                "away_score":   away.get("score"),
                "scorers":      [],
                "venue":        comp.get("venue", {}).get("fullName", ""),
                "home": {
                    "name": home.get("team", {}).get("displayName", ""),
                    "logo": home.get("team", {}).get("logo", ""),
                },
                "away": {
                    "name": away.get("team", {}).get("displayName", ""),
                    "logo": away.get("team", {}).get("logo", ""),
                },
            }

            try:
                import re
                scorers = []
                for p in (comp.get("plays") or []):
                    ptype = (p.get("type") or {}).get("name", "").lower()
                    text  = (p.get("text") or "").lower()
                    if "goal" in ptype or "goal" in text or "score" in ptype:
                        athlete = p.get("athlete") or p.get("athletes")
                        if isinstance(athlete, dict):
                            player_name = athlete.get("displayName") or athlete.get("fullName")
                        elif isinstance(athlete, list) and athlete:
                            player_name = athlete[0].get("displayName") or athlete[0].get("fullName")
                        else:
                            player_name = None
                        team_name = (p.get("team") or {}).get("displayName")
                        minute = None
                        if p.get("clock", {}).get("displayValue"):
                            minute = p["clock"]["displayValue"]
                        else:
                            m = re.search(r"(\d{1,2}(?:\+\d{1,2})?)'", p.get("text") or "")
                            if m:
                                minute = m.group(1) + "'"
                        if player_name or team_name:
                            scorers.append({"team": team_name, "player": player_name, "minute": minute})
                if scorers:
                    match["scorers"] = scorers
            except Exception:
                pass

            matches.append(match)
        except Exception as e:
            logging.warning(f"Skipped event: {e}")

    return matches


@app.get("/team-stats/{team_name}")
def team_stats(team_name: str):
    try:
        conn        = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur         = conn.cursor()
        like_name   = f"%{team_name.strip().lower()}%"

        cur.execute("""
            SELECT won, goals_for, team FROM standings
            WHERE LOWER(team) = LOWER(?) OR LOWER(team) LIKE ?
            ORDER BY CASE WHEN LOWER(team) = LOWER(?) THEN 0 ELSE 1 END
            LIMIT 1
        """, (team_name, like_name, team_name))
        standing     = cur.fetchone()
        matched_team = standing["team"] if standing else team_name

        cur.execute("""
            SELECT scorer, COUNT(*) as goal_count
            FROM goals
            WHERE LOWER(team_name) = LOWER(?) OR LOWER(team_name) LIKE ?
            GROUP BY scorer ORDER BY goal_count DESC LIMIT 1
        """, (matched_team, like_name))
        top_scorer_row = cur.fetchone()
        conn.close()

        return {
            "team":             matched_team,
            "wins":             standing["won"] if standing else 0,
            "goals_scored":     standing["goals_for"] if standing else 0,
            "top_scorer":       top_scorer_row["scorer"] if top_scorer_row else None,
            "top_scorer_goals": top_scorer_row["goal_count"] if top_scorer_row else 0,
        }
    except Exception as e:
        logging.exception(f"Error fetching team stats for {team_name}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/leaderboards")
def leaderboards():
    """
    Fixed, deterministic leaderboard queries — bypasses the LLM pipeline entirely
    (no routing/SQL-gen/verify calls, no provider rate-limit exposure) since these
    are well-known questions with a stable shape.
    """
    try:
        stats_conn = sqlite3.connect(STATS_DB_PATH)
        stats_conn.row_factory = sqlite3.Row
        stats_cur = stats_conn.cursor()

        stats_cur.execute("""
            SELECT p.display_name AS name, p.team_name AS team,
                   ROUND(SUM(msv.numeric_value), 2) AS value
            FROM players p
            JOIN match_player_stats mps ON p.player_id = mps.player_id
            JOIN match_world_cup_flag mf ON mf.match_id = mps.match_id AND mf.is_world_cup = 1
            JOIN match_stat_values msv ON mps.id = msv.match_player_stats_id
            WHERE msv.stat_key = 'expectedGoals'
            GROUP BY p.player_id
            ORDER BY value DESC
            LIMIT 10
        """)
        top_players_xg = [dict(r) for r in stats_cur.fetchall()]

        stats_cur.execute("""
            SELECT p.team_name AS team, ROUND(SUM(msv.numeric_value), 2) AS value
            FROM players p
            JOIN match_player_stats mps ON p.player_id = mps.player_id
            JOIN match_world_cup_flag mf ON mf.match_id = mps.match_id AND mf.is_world_cup = 1
            JOIN match_stat_values msv ON mps.id = msv.match_player_stats_id
            WHERE msv.stat_key = 'expectedGoals'
            GROUP BY p.team_name
            ORDER BY value DESC
            LIMIT 10
        """)
        top_teams_xg = [dict(r) for r in stats_cur.fetchall()]

        stats_cur.execute("""
            SELECT p.display_name AS name, p.team_name AS team,
                   ROUND(AVG(msv.numeric_value), 2) AS value,
                   COUNT(DISTINCT mps.match_id) AS matches
            FROM players p
            JOIN match_player_stats mps ON p.player_id = mps.player_id
            JOIN match_world_cup_flag mf ON mf.match_id = mps.match_id AND mf.is_world_cup = 1
            JOIN match_stat_values msv ON mps.id = msv.match_player_stats_id
            WHERE msv.stat_key = 'fsRating'
            GROUP BY p.player_id
            HAVING matches >= 2
            ORDER BY value DESC
            LIMIT 10
        """)
        top_rated_players = [dict(r) for r in stats_cur.fetchall()]
        stats_conn.close()

        # goals come from the primary (Zafronix) DB, not worldcup_stats.db — its
        # match results are authoritative for all 48 teams, unaffected by the
        # Flashscore sync's current coverage gaps
        primary_conn = sqlite3.connect(DB_PATH)
        primary_conn.row_factory = sqlite3.Row
        primary_cur = primary_conn.cursor()
        primary_cur.execute("""
            SELECT team, SUM(score) AS value FROM (
                SELECT home_team AS team, home_score AS score FROM matches WHERE status = 'finished'
                UNION ALL
                SELECT away_team AS team, away_score AS score FROM matches WHERE status = 'finished'
            )
            GROUP BY team
            ORDER BY value DESC
            LIMIT 10
        """)
        top_scoring_teams = [dict(r) for r in primary_cur.fetchall()]
        primary_conn.close()

        return {
            "top_players_xg": top_players_xg,
            "top_teams_xg": top_teams_xg,
            "top_rated_players": top_rated_players,
            "top_scoring_teams": top_scoring_teams,
        }
    except Exception as e:
        logging.exception("Error building leaderboards")
        raise HTTPException(status_code=500, detail=str(e))


_FINDER_OPERATORS = {"gte": ">=", "gt": ">", "lte": "<=", "lt": "<", "eq": "="}
_FINDER_MAX_FILTERS = 5


@app.get("/player-finder/options")
def player_finder_options():
    """Stat keys available for filtering, grouped by category, for the finder UI."""
    try:
        conn = sqlite3.connect(STATS_DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT stat_key, label, category FROM stat_types
            WHERE category != 'unknown'
            ORDER BY category, label
        """)
        stats = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {"stats": stats}
    except Exception as e:
        logging.exception("Error fetching player-finder options")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/player-finder")
async def player_finder(request: Request):
    """
    Percentile/threshold-style player search — deterministic SQL against
    tournament_player_stats + tournament_stat_values, bypasses the LLM pipeline
    entirely. stat_key is always bound as a query parameter (never interpolated
    into SQL text) and additionally whitelisted against stat_types.
    """
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    filters = payload.get("filters") if isinstance(payload, dict) else None
    if not isinstance(filters, list) or not filters:
        raise HTTPException(status_code=400, detail="'filters' must be a non-empty list")
    if len(filters) > _FINDER_MAX_FILTERS:
        raise HTTPException(status_code=400, detail=f"Max {_FINDER_MAX_FILTERS} filters allowed")

    parsed = []
    for f in filters:
        stat_key = f.get("stat_key") if isinstance(f, dict) else None
        operator = f.get("operator") if isinstance(f, dict) else None
        value = f.get("value") if isinstance(f, dict) else None
        if not stat_key or operator not in _FINDER_OPERATORS:
            raise HTTPException(status_code=400, detail="Each filter needs a valid stat_key and operator")
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Filter value must be a number")
        parsed.append((stat_key, operator, value))

    try:
        conn = sqlite3.connect(STATS_DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT stat_key, label FROM stat_types")
        known = {row["stat_key"]: row["label"] for row in cur.fetchall()}
        for stat_key, _, _ in parsed:
            if stat_key not in known:
                raise HTTPException(status_code=400, detail=f"Unknown stat_key: {stat_key}")

        # join_params and where_params are kept separate (not interleaved per
        # filter) because sqlite binds `?` positionally against the final SQL
        # text, where all JOINs precede all WHEREs regardless of filter order.
        joins, wheres, selects = [], [], []
        join_params, where_params = [], []
        for i, (stat_key, operator, value) in enumerate(parsed):
            alias = f"tsv{i}"
            joins.append(
                f"JOIN tournament_stat_values {alias} "
                f"ON {alias}.tournament_player_stats_id = tps.id AND {alias}.stat_key = ?"
            )
            join_params.append(stat_key)
            wheres.append(f"{alias}.numeric_value {_FINDER_OPERATORS[operator]} ?")
            where_params.append(value)
            selects.append(f"{alias}.numeric_value AS filter_{i}")

        sql = f"""
            SELECT p.display_name AS name, p.team_name AS team, p.position AS position,
                   tps.matches_played, ROUND(tps.avg_rating, 2) AS avg_rating,
                   {', '.join(selects)}
            FROM tournament_player_stats tps
            JOIN players p ON p.player_id = tps.player_id
            {' '.join(joins)}
            WHERE {' AND '.join(wheres)}
            ORDER BY tps.avg_rating DESC
            LIMIT 100
        """
        cur.execute(sql, join_params + where_params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        return {
            "rows": rows,
            "filters": [
                {"stat_key": k, "label": known[k], "operator": o, "value": v}
                for k, o, v in parsed
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error running player finder query")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query")
async def run_query(request: Request):
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    question = payload.get("question") if isinstance(payload, dict) else None
    if not isinstance(question, str) or not question.strip():
        raise HTTPException(status_code=400, detail="'question' must be a non-empty string")

    mode = payload.get("mode") if isinstance(payload, dict) else None
    if mode not in ("player", "general", None):
        mode = None

    logging.info("Received query: %s (mode=%s)", question, mode)
    return run(question, mode)

# ESPN's season.slug -> our existing stage key/display-name scheme, so the
# frontend (Bracket.jsx) needs zero changes despite the data source swap.
_BRACKET_STAGE_MAP = {
    "round-of-32":      ("r32",        "Round of 32"),
    "round-of-16":      ("r16",        "Round of 16"),
    "quarterfinals":    ("qf",         "Quarter Finals"),
    "semifinals":       ("sf",         "Semi Finals"),
    "3rd-place-match":  ("thirdPlace", "Third Place"),
    "final":            ("final",     "Final"),
}
_BRACKET_STAGE_ORDER = ["r32", "r16", "qf", "sf", "thirdPlace", "final"]
_BRACKET_STAGE_NAMES = {key: name for key, name in _BRACKET_STAGE_MAP.values()}


@app.get("/bracket")
def bracket():
    """
    Knockout bracket sourced from ESPN's scoreboard (same feed as /today-matches)
    instead of the daily-synced worldcup.db — ESPN updates within minutes of a
    result, so the bracket reflects reality immediately instead of up to 24h later.
    Group-stage events from this same date range are deliberately skipped; only
    the knockout-stage slugs above are included.
    """
    try:
        res = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard",
            params={"dates": "20260624-20260720"},
            timeout=10,
        )
        res.raise_for_status()
        events = res.json().get("events", [])
    except Exception as e:
        logging.exception("Failed to fetch bracket from ESPN API")
        raise HTTPException(status_code=502, detail=f"ESPN API error: {e}")

    stages = {key: [] for key in _BRACKET_STAGE_ORDER}
    for event in events:
        slug = event.get("season", {}).get("slug")
        mapped = _BRACKET_STAGE_MAP.get(slug)
        if not mapped:
            continue
        key, _ = mapped

        comp = event.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])
        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})
        status = comp.get("status", {}).get("type", {})

        def _score(c):
            v = c.get("score")
            return int(v) if v not in (None, "") else None

        stages[key].append({
            "id":          event.get("id"),
            "home":        home.get("team", {}).get("displayName") or "TBD",
            "away":        away.get("team", {}).get("displayName") or "TBD",
            "home_score":  _score(home),
            "away_score":  _score(away),
            "status":      status.get("description"),
            "finished":    bool(status.get("completed")),
            # explicit winner flag (not just score comparison) since a penalty-shootout
            # win still reports a tied regulation/ET score in home_score/away_score
            "home_winner": bool(home.get("winner")),
            "away_winner": bool(away.get("winner")),
        })

    return {
        "stages": [
            {"name": _BRACKET_STAGE_NAMES[key], "key": key, "matches": stages[key]}
            for key in _BRACKET_STAGE_ORDER
        ]
    }


# Serves the built frontend (npm run build -> frontend/dist) from this same app,
# so in production there's one origin and no dev proxy / CORS to configure. Must
# be mounted last — every @app.get/@app.post above takes precedence over it, and
# this catches everything else (the SPA's index.html and its JS/CSS/image assets).
# Only mounts if the frontend has actually been built; local dev running
# `npm run dev` separately doesn't need this at all.
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
