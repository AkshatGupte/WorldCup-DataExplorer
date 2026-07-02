import requests, os
from datetime import date, timedelta
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
    r = requests.get(f"{BASE}/{endpoint}", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()

def update_recent_matches(cur):
    print("Checking for recently finished match updates...")
    data    = get("matches", {"year": 2026})
    matches = data["data"]

    today          = date.today()
    yesterday      = today - timedelta(days=1)
    relevant_dates = {today.isoformat(), yesterday.isoformat()}

    updated_ids = []

    for m in matches:
        if m.get("date") not in relevant_dates:
            continue

        mid = m["id"]
        cur.execute("SELECT status, home_score, away_score FROM matches WHERE id=?", (mid,))
        existing = cur.fetchone()

        if existing and existing["status"] == m.get("status") \
           and existing["home_score"] == m.get("homeScore") \
           and existing["away_score"] == m.get("awayScore"):
            continue

        updated_ids.append(mid)

        cur.execute("""
            INSERT INTO matches
                (id, match_no, date, kickoff_utc, stage, home_team, away_team,
                 home_score, away_score, stadium, city, country, attendance,
                 referee_name, referee_country, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status,
                home_score=excluded.home_score,
                away_score=excluded.away_score,
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

        # also refresh goals/cards/lineups/subs/stats for this specific match
        cur.execute("DELETE FROM goals WHERE match_id=?", (mid,))
        cur.execute("DELETE FROM cards WHERE match_id=?", (mid,))
        cur.execute("DELETE FROM lineups WHERE match_id=?", (mid,))
        cur.execute("DELETE FROM substitutions WHERE match_id=?", (mid,))
        cur.execute("DELETE FROM match_stats WHERE match_id=?", (mid,))

        for g in m.get("goals") or []:
            team_name = m["homeTeam"] if g["team"] == "home" else m["awayTeam"]
            cur.execute("""
                INSERT INTO goals (match_id, minute, team_side, team_name, scorer)
                VALUES (?, ?, ?, ?, ?)
            """, (mid, g.get("minute"), g["team"], team_name, g.get("scorer")))

        for c in m.get("cards") or []:
            team_name = m["homeTeam"] if c["team"] == "home" else m["awayTeam"]
            cur.execute("""
                INSERT INTO cards (match_id, minute, team_side, team_name, player, color)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (mid, c.get("minute"), c["team"], team_name, c.get("player"), c.get("color")))

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

        for s in m.get("substitutions") or []:
            team_name = m["homeTeam"] if s["team"] == "home" else m["awayTeam"]
            cur.execute("""
                INSERT INTO substitutions (match_id, minute, team_side, team_name, player_on, player_off)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (mid, s.get("minute"), s["team"], team_name, s.get("on"), s.get("off")))

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

    print(f"  {len(updated_ids)} match(es) updated: {updated_ids}")

def update_recent():
    init_db()
    conn = get_conn()
    cur  = conn.cursor()
    update_recent_matches(cur)
    conn.commit()
    conn.close()
    print("Recent update complete.")

if __name__ == "__main__":
    update_recent()