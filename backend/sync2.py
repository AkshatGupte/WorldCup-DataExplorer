import requests, os
from pathlib import Path
from dotenv import load_dotenv

try:
    from .db2 import get_conn, init_footballdata_tables
except ImportError:
    from db2 import get_conn, init_footballdata_tables

load_dotenv(Path(__file__).resolve().parent / ".env")

KEY     = os.getenv("SPORTS_KEY")
BASE    = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": KEY}

def get(endpoint, params={}):
    r = requests.get(f"{BASE}/{endpoint}", headers=HEADERS, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def sync_matches(cur):
    print("Syncing football-data matches...")
    data    = get("competitions/WC/matches", {"season": 2026})
    matches = data["matches"]

    for m in matches:
        score = m.get("score", {}).get("fullTime", {})
        cur.execute("""
            INSERT INTO fd_matches
                (id, utc_date, status, matchday, stage, group_name,
                 home_team, away_team, home_team_crest, away_team_crest,
                 home_score, away_score, winner, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status,
                home_score=excluded.home_score,
                away_score=excluded.away_score,
                winner=excluded.winner,
                last_updated=excluded.last_updated
        """, (
            m["id"], m.get("utcDate"), m.get("status"), m.get("matchday"),
            m.get("stage"), m.get("group"),
            m["homeTeam"].get("name"), m["awayTeam"].get("name"),
            m["homeTeam"].get("crest"), m["awayTeam"].get("crest"),
            score.get("home"), score.get("away"),
            m.get("score", {}).get("winner"), m.get("lastUpdated")
        ))
    print(f"  {len(matches)} matches synced.")

def sync_standings(cur):
    print("Syncing football-data standings...")
    data = get("competitions/WC/standings", {"season": 2026})
    count = 0
    for group in data.get("standings", []):
        group_name = group.get("group")
        for row in group.get("table", []):
            cur.execute("""
                INSERT INTO fd_standings
                    (group_name, team, team_crest, position, played_games,
                     won, draw, lost, points, goals_for, goals_against, goal_difference)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                group_name, row["team"]["name"], row["team"].get("crest"),
                row.get("position"), row.get("playedGames"),
                row.get("won"), row.get("draw"), row.get("lost"),
                row.get("points"), row.get("goalsFor"),
                row.get("goalsAgainst"), row.get("goalDifference")
            ))
            count += 1
    print(f"  {count} standing rows synced.")

def sync_scorers(cur):
    print("Syncing football-data top scorers...")
    data = get("competitions/WC/scorers", {"season": 2026, "limit": 50})
    for s in data.get("scorers", []):
        cur.execute("""
            INSERT INTO fd_scorers (player_name, team, goals, assists, penalties)
            VALUES (?, ?, ?, ?, ?)
        """, (
            s["player"]["name"], s["team"]["name"],
            s.get("goals"), s.get("assists"), s.get("penalties")
        ))
    print(f"  {len(data.get('scorers', []))} scorers synced.")

def sync():
    init_footballdata_tables()
    conn = get_conn()
    cur  = conn.cursor()

    cur.execute("DELETE FROM fd_standings")
    cur.execute("DELETE FROM fd_scorers")

    sync_matches(cur)
    sync_standings(cur)
    sync_scorers(cur)

    conn.commit()
    conn.close()
    print("\nfootball-data.org sync complete.")

if __name__ == "__main__":
    sync()
