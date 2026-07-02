import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "worldcup_fd.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_footballdata_tables():
    conn = get_conn()
    cur  = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS fd_matches (
        id              INTEGER PRIMARY KEY,
        utc_date        TEXT,
        status          TEXT,
        matchday        INTEGER,
        stage           TEXT,
        group_name      TEXT,
        home_team       TEXT,
        away_team       TEXT,
        home_team_crest TEXT,
        away_team_crest TEXT,
        home_score      INTEGER,
        away_score      INTEGER,
        winner          TEXT,
        last_updated    TEXT
    );

    CREATE TABLE IF NOT EXISTS fd_standings (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name      TEXT,
        team            TEXT,
        team_crest      TEXT,
        position        INTEGER,
        played_games    INTEGER,
        won             INTEGER,
        draw            INTEGER,
        lost            INTEGER,
        points          INTEGER,
        goals_for       INTEGER,
        goals_against   INTEGER,
        goal_difference INTEGER
    );

    CREATE TABLE IF NOT EXISTS fd_scorers (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        player_name TEXT,
        team        TEXT,
        goals       INTEGER,
        assists     INTEGER,
        penalties   INTEGER
    );
    """)
    conn.commit()
    conn.close()
    print("football-data.org tables initialized.")

if __name__ == "__main__":
    init_footballdata_tables()
