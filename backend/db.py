import sqlite3
from pathlib import Path 

DB_PATH       = "worldcup.db"
STATS_DB_PATH = "worldcup_stats.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def execute_primary_sql(sql: str) -> list[dict]:
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(f"ATTACH DATABASE '{STATS_DB_PATH}' AS stats")
    cur.execute(sql)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def execute_stats_sql(sql: str) -> list[dict]:
    conn = sqlite3.connect(STATS_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()
    cur.execute(sql)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS teams (
        name TEXT PRIMARY KEY, code TEXT, iso TEXT,
        confederation TEXT, group_name TEXT,
        coach_name TEXT, coach_country TEXT
    );
    CREATE TABLE IF NOT EXISTS matches (
        id TEXT PRIMARY KEY, match_no INTEGER, date TEXT,
        kickoff_utc TEXT, stage TEXT, home_team TEXT, away_team TEXT,
        home_score INTEGER, away_score INTEGER, stadium TEXT,
        city TEXT, country TEXT, attendance INTEGER,
        referee_name TEXT, referee_country TEXT, status TEXT
    );
    CREATE TABLE IF NOT EXISTS standings (
        group_name TEXT, team TEXT, played INTEGER, won INTEGER,
        drawn INTEGER, lost INTEGER, goals_for INTEGER,
        goals_against INTEGER, goal_difference INTEGER, points INTEGER,
        fair_play INTEGER, position INTEGER, advanced INTEGER,
        PRIMARY KEY (group_name, team)
    );
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT, team TEXT, name TEXT,
        position TEXT, jersey INTEGER, born TEXT, age INTEGER,
        club_name TEXT, club_country TEXT, captain INTEGER
    );
    CREATE TABLE IF NOT EXISTS match_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT, match_id TEXT, team_side TEXT,
        team_name TEXT, possession_pct INTEGER, shots_total INTEGER,
        shots_on_goal INTEGER, shots_off_goal INTEGER, shots_blocked INTEGER,
        shots_inside_box INTEGER, shots_outside_box INTEGER, corners INTEGER,
        offsides INTEGER, fouls INTEGER, yellow_cards INTEGER, red_cards INTEGER,
        goalkeeper_saves INTEGER, passes_total INTEGER, passes_accurate INTEGER,
        passes_pct INTEGER, xg REAL, FOREIGN KEY (match_id) REFERENCES matches(id)
    );
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT, match_id TEXT, minute INTEGER,
        team_side TEXT, team_name TEXT, scorer TEXT,
        FOREIGN KEY (match_id) REFERENCES matches(id)
    );
    CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT, match_id TEXT, minute INTEGER,
        team_side TEXT, team_name TEXT, player TEXT, color TEXT,
        FOREIGN KEY (match_id) REFERENCES matches(id)
    );
    CREATE TABLE IF NOT EXISTS lineups (
        id INTEGER PRIMARY KEY AUTOINCREMENT, match_id TEXT, team_side TEXT,
        team_name TEXT, player TEXT, number INTEGER, position TEXT,
        starter INTEGER, captain INTEGER,
        FOREIGN KEY (match_id) REFERENCES matches(id)
    );
    CREATE TABLE IF NOT EXISTS substitutions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, match_id TEXT, minute INTEGER,
        team_side TEXT, team_name TEXT, player_on TEXT, player_off TEXT,
        FOREIGN KEY (match_id) REFERENCES matches(id)
    );
    """)
    conn.commit()
    conn.close()
    print("DB initialized.")
