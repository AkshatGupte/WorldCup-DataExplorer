import requests, sqlite3, os
from pathlib import Path
from dotenv import load_dotenv

try:
    from .db import get_conn, init_db
except ImportError:
    from db import get_conn, init_db

load_dotenv(Path(__file__).resolve().parent / ".env")

KEY     = os.getenv("ZAFRONIX_KEY")
BASE    = "https://api.zafronix.com/fifa/worldcup/v1"
HEADERS = {"X-API-Key": KEY}

def get(endpoint, params={}):
    r = requests.get(f"{BASE}/{endpoint}", headers=HEADERS, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def sync_teams(cur):
    print("Syncing teams...")
    teams = get("teams", {"tournament": 2026})
    for t in teams:
        cur.execute("""
            INSERT INTO teams (name, code, iso, confederation, group_name, coach_name, coach_country)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                group_name=excluded.group_name,
                coach_name=excluded.coach_name
        """, (
            t["name"], t.get("code"), t.get("iso"), t.get("confederation"),
            t.get("groupStage", {}).get("group"),
            t.get("coach", {}).get("name"), t.get("coach", {}).get("country")
        ))

        for p in t.get("squad", []):
            cur.execute("""
                INSERT INTO players (team, name, position, jersey, born, age, club_name, club_country, captain)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                t["name"], p["name"], p.get("position"), p.get("jersey"),
                p.get("born"), p.get("ageAtTournament"),
                p.get("club", {}).get("name"), p.get("club", {}).get("country"),
                1 if p.get("captain") else 0
            ))

    print(f"  {len(teams)} teams synced.")

def sync_matches(cur):
    print("Syncing matches...")
    data    = get("matches", {"year": 2026})
    matches = data["data"]

    for m in matches:
        mid = m["id"]

        cur.execute("""
            INSERT INTO matches
                (id, match_no, date, kickoff_utc, stage, home_team, away_team,
                 home_score, away_score, stadium, city, country, attendance,
                 referee_name, referee_country, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                home_score=excluded.home_score,
                away_score=excluded.away_score,
                status=excluded.status,
                attendance=excluded.attendance
        """, (
            mid, m.get("matchNo"), m.get("date"), m.get("kickoffUtc"),
            m.get("stage"), m.get("homeTeam"), m.get("awayTeam"),
            m.get("homeScore"), m.get("awayScore"), m.get("stadium"),
            m.get("city"), m.get("country"), m.get("attendance"),
            m.get("referee", {}).get("name") if m.get("referee") else None,
            m.get("referee", {}).get("country") if m.get("referee") else None,
            m.get("status")
        ))

        # goals
        for g in m.get("goals") or []:
            team_name = m["homeTeam"] if g["team"] == "home" else m["awayTeam"]
            cur.execute("""
                INSERT INTO goals (match_id, minute, team_side, team_name, scorer)
                VALUES (?, ?, ?, ?, ?)
            """, (mid, g.get("minute"), g["team"], team_name, g.get("scorer")))

        # cards
        for c in m.get("cards") or []:
            team_name = m["homeTeam"] if c["team"] == "home" else m["awayTeam"]
            cur.execute("""
                INSERT INTO cards (match_id, minute, team_side, team_name, player, color)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (mid, c.get("minute"), c["team"], team_name, c.get("player"), c.get("color")))

        # lineups
        for side in ["home", "away"]:
            team_name = m["homeTeam"] if side == "home" else m["awayTeam"]
            for p in (m.get("lineups") or {}).get(side, []):
                cur.execute("""
                    INSERT INTO lineups (match_id, team_side, team_name, player, number, position, starter, captain)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    mid, side, team_name, p["player"], p.get("number"),
                    p.get("position"), 1 if p.get("starter") else 0,
                    1 if p.get("captain") else 0
                ))

        # substitutions
        for s in m.get("substitutions") or []:
            team_name = m["homeTeam"] if s["team"] == "home" else m["awayTeam"]
            cur.execute("""
                INSERT INTO substitutions (match_id, minute, team_side, team_name, player_on, player_off)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (mid, s.get("minute"), s["team"], team_name, s.get("on"), s.get("off")))

        # match stats
        for side in ["home", "away"]:
            stats = (m.get("statistics") or {}).get(side)
            if not stats:
                continue
            team_name = m["homeTeam"] if side == "home" else m["awayTeam"]
            cur.execute("""
                INSERT INTO match_stats
                    (match_id, team_side, team_name, possession_pct, shots_total,
                     shots_on_goal, shots_off_goal, shots_blocked, shots_inside_box,
                     shots_outside_box, corners, offsides, fouls, yellow_cards,
                     red_cards, goalkeeper_saves, passes_total, passes_accurate,
                     passes_pct, xg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mid, side, team_name,
                stats.get("possessionPct"), stats.get("shotsTotal"),
                stats.get("shotsOnGoal"), stats.get("shotsOffGoal"),
                stats.get("shotsBlocked"), stats.get("shotsInsideBox"),
                stats.get("shotsOutsideBox"), stats.get("corners"),
                stats.get("offsides"), stats.get("fouls"),
                stats.get("yellowCards"), stats.get("redCards"),
                stats.get("goalkeeperSaves"), stats.get("passesTotal"),
                stats.get("passesAccurate"), stats.get("passesPct"),
                stats.get("expectedGoals")
            ))

    print(f"  {len(matches)} matches synced.")

def sync_standings(cur):
    print("Syncing standings...")
    data  = get("standings", {"year": 2026})
    count = 0
    for group_name, rows in data["groups"].items():
        for row in rows:
            cur.execute("""
                INSERT INTO standings
                    (group_name, team, played, won, drawn, lost, goals_for,
                     goals_against, goal_difference, points, fair_play, position, advanced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_name, team) DO UPDATE SET
                    played=excluded.played, won=excluded.won,
                    drawn=excluded.drawn, lost=excluded.lost,
                    goals_for=excluded.goals_for, goals_against=excluded.goals_against,
                    goal_difference=excluded.goal_difference, points=excluded.points,
                    position=excluded.position, advanced=excluded.advanced
            """, (
                group_name, row["team"], row["played"], row["won"],
                row["drawn"], row["lost"], row["goalsFor"], row["goalsAgainst"],
                row["goalDifference"], row["points"], row.get("fairPlay"),
                row["position"], 1 if row.get("advanced") else 0
            ))
            count += 1
    print(f"  {count} standing rows synced.")

def sync():
    init_db()
    conn = get_conn()
    cur  = conn.cursor()
    sync_teams(cur)
    sync_matches(cur)
    sync_standings(cur)
    conn.commit()
    conn.close()
    print("\nSync complete.")

if __name__ == "__main__":
    sync()
