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

@app.get("/bracket")
def bracket():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT id, stage, home_team, away_team,
                   home_score, away_score, status
            FROM matches
            WHERE stage NOT LIKE 'group_%'
            ORDER BY
                CASE stage
                    WHEN 'r32'        THEN 1
                    WHEN 'r16'        THEN 2
                    WHEN 'qf'         THEN 3
                    WHEN 'sf'         THEN 4
                    WHEN 'thirdPlace' THEN 5
                    WHEN 'final'      THEN 6
                END, id
        """)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        stages = {}
        for r in rows:
            s = r["stage"]
            if s not in stages:
                stages[s] = []
            stages[s].append({
                "id":         r["id"],
                "home":       r["home_team"] or "TBD",
                "away":       r["away_team"] or "TBD",
                "home_score": r["home_score"],
                "away_score": r["away_score"],
                "status":     r["status"],
                "finished":   r["status"] == "finished"
            })

        return {
            "stages": [
                {"name": "Round of 32",    "key": "r32",        "matches": stages.get("r32", [])},
                {"name": "Round of 16",    "key": "r16",        "matches": stages.get("r16", [])},
                {"name": "Quarter Finals", "key": "qf",         "matches": stages.get("qf", [])},
                {"name": "Semi Finals",    "key": "sf",         "matches": stages.get("sf", [])},
                {"name": "Third Place",    "key": "thirdPlace", "matches": stages.get("thirdPlace", [])},
                {"name": "Final",          "key": "final",      "matches": stages.get("final", [])},
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
