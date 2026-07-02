"""
SQLite helpers for worldcup_stats.db — player profiles and statistics.

This database is separate from worldcup.db and stores SportDB.dev player data:
profiles, per-match stats, tournament aggregates, goalkeeper metrics, and awards.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "worldcup_stats.db"

# SportDB Flashscore tournament identifiers for FIFA World Cup 2026.
TOURNAMENT_ID = "lvUBR5F8"
TOURNAMENT_NAME = "FIFA World Cup 2026"
TOURNAMENT_SEASON = "2026"

# Known goalkeeper stat keys (also stored in goalkeeper_match_stats).
GOALKEEPER_STAT_KEYS = frozenset(
    {
        "expectedGoalsOnTargetFaced",
        "goalsConceded",
        "goalsPrevented",
        "keeperSweeperTotal",
        "keeperThrowsTotal",
        "punchesTotal",
        "savesTotal",
    }
)

STAT_TYPE_SEED: list[tuple[str, str, str]] = [
    ("fsRating", "Rating", "general"),
    ("matchMinutesPlayed", "Minutes played", "general"),
    ("touchesTotal", "Touches", "general"),
    ("goals", "Goals", "attacking"),
    ("assistsGoal", "Assists", "attacking"),
    ("expectedGoals", "Expected goals (xG)", "attacking"),
    ("expectedGoalsOnTarget", "Expected goals on target (xGOT)", "attacking"),
    ("expectedAssists", "Expected assists (xA)", "attacking"),
    ("shotsTotal", "Total shots", "attacking"),
    ("shotsOnTarget", "Shots on target", "attacking"),
    ("shotsOffTarget", "Shots off target", "attacking"),
    ("shotsBlocked", "Blocked shots", "attacking"),
    ("shotsBoxIn", "Shots inside box", "attacking"),
    ("shotsBoxOut", "Shots outside box", "attacking"),
    ("shotsHead", "Headed shots", "attacking"),
    ("bigChancesCreated", "Big chances created", "attacking"),
    ("bigChancesMissed", "Big chances missed", "attacking"),
    ("keyPasses", "Key passes", "attacking"),
    ("offsides", "Offsides", "attacking"),
    ("touchesBoxOpposite", "Touches in opposition box", "attacking"),
    ("dribblesTotal", "Dribbles attempted", "attacking"),
    ("dribblesWon", "Dribbles won", "attacking"),
    ("dribblesEfficiency", "Dribble success %", "attacking"),
    ("passesTotal", "Total passes", "passing"),
    ("passesAccurate", "Accurate passes", "passing"),
    ("passesAccuracy", "Pass accuracy %", "passing"),
    ("passesFinalThirdTotal", "Final third passes", "passing"),
    ("passesFinalThirdAccurate", "Final third passes accurate", "passing"),
    ("passesFinalThirdAccuracy", "Final third pass accuracy %", "passing"),
    ("longBallsTotal", "Long balls", "passing"),
    ("longBallsAccurate", "Long balls accurate", "passing"),
    ("longBallsAccuracy", "Long ball accuracy %", "passing"),
    ("crossesTotal", "Crosses", "passing"),
    ("crossesAccurate", "Crosses accurate", "passing"),
    ("crossesAccuracy", "Cross accuracy %", "passing"),
    ("tacklesTotal", "Tackles", "defensive"),
    ("tacklesWon", "Tackles won", "defensive"),
    ("tacklesEfficiency", "Tackle success %", "defensive"),
    ("interceptions", "Interceptions", "defensive"),
    ("clearances", "Clearances", "defensive"),
    ("duelsTotal", "Duels", "defensive"),
    ("duelsWon", "Duels won", "defensive"),
    ("duelsEfficiency", "Duels won %", "defensive"),
    ("duelsGroundTotal", "Ground duels", "defensive"),
    ("duelsGroundWon", "Ground duels won", "defensive"),
    ("duelsGroundEfficiency", "Ground duels won %", "defensive"),
    ("duelsAerialTotal", "Aerial duels", "defensive"),
    ("duelsAerialWon", "Aerial duels won", "defensive"),
    ("duelsAerialEfficiency", "Aerial duels won %", "defensive"),
    ("cardsYellow", "Yellow cards", "disciplinary"),
    ("cardsRed", "Red cards", "disciplinary"),
    ("foulsCommitted", "Fouls committed", "disciplinary"),
    ("foulsSuffered", "Fouls suffered", "disciplinary"),
    ("errorsLeadToGoal", "Errors leading to goal", "disciplinary"),
    ("errorsLeadToShot", "Errors leading to shot", "disciplinary"),
    ("goalsOwn", "Own goals", "disciplinary"),
    ("savesTotal", "Saves", "goalkeeping"),
    ("goalsConceded", "Goals conceded", "goalkeeping"),
    ("goalsPrevented", "Goals prevented", "goalkeeping"),
    ("expectedGoalsOnTargetFaced", "Expected goals on target faced", "goalkeeping"),
    ("keeperSweeperTotal", "Keeper sweeper actions", "goalkeeping"),
    ("keeperThrowsTotal", "Throws", "goalkeeping"),
    ("punchesTotal", "Punches", "goalkeeping"),
]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def execute_sql(sql: str, params: tuple = ()) -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


SCHEMA_VERSION = 2


def _current_schema_version(cur: sqlite3.Cursor) -> int | None:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    )
    if not cur.fetchone():
        return None
    cur.execute("SELECT version FROM schema_version")
    row = cur.fetchone()
    return int(row[0]) if row else None


def _drop_legacy_stats_tables(cur: sqlite3.Cursor) -> None:
    """Remove tables from the previous worldcup_stats.db layout."""
    cur.executescript(
        """
        PRAGMA foreign_keys = OFF;
        DROP TABLE IF EXISTS goalkeeper_stat_values;
        DROP TABLE IF EXISTS goalkeeper_match_stats;
        DROP TABLE IF EXISTS tournament_stat_values;
        DROP TABLE IF EXISTS tournament_player_stats;
        DROP TABLE IF EXISTS match_stat_values;
        DROP TABLE IF EXISTS match_player_stats;
        DROP TABLE IF EXISTS awards;
        DROP TABLE IF EXISTS sync_log;
        DROP TABLE IF EXISTS player_stats;
        DROP TABLE IF EXISTS players;
        DROP TABLE IF EXISTS stat_types;
        DROP TABLE IF EXISTS tournaments;
        DROP TABLE IF EXISTS schema_version;
        PRAGMA foreign_keys = ON;
        """
    )


def init_db() -> None:
    """Create tables, indexes, and stat-type seed data if they do not exist."""
    conn = get_conn()
    cur = conn.cursor()

    version = _current_schema_version(cur)
    if version != SCHEMA_VERSION:
        _drop_legacy_stats_tables(cur)

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS tournaments (
            tournament_id   TEXT PRIMARY KEY,
            name              TEXT NOT NULL,
            season            TEXT,
            slug              TEXT,
            updated_at        TEXT
        );

        CREATE TABLE IF NOT EXISTS stat_types (
            stat_key          TEXT PRIMARY KEY,
            label             TEXT,
            category          TEXT
        );

        CREATE TABLE IF NOT EXISTS players (
            player_id         TEXT PRIMARY KEY,
            full_name         TEXT,
            display_name      TEXT,
            first_name        TEXT,
            last_name         TEXT,
            slug              TEXT,
            nationality       TEXT,
            nationality_id    TEXT,
            team_id           TEXT,
            team_name         TEXT,
            jersey_number     INTEGER,
            position          TEXT,
            is_goalkeeper     INTEGER DEFAULT 0,
            date_of_birth     TEXT,
            age               INTEGER,
            height            INTEGER,
            weight            INTEGER,
            preferred_foot    TEXT,
            club_name         TEXT,
            club_id           TEXT,
            image_url         TEXT,
            profile_link      TEXT,
            market_value      TEXT,
            player_status     TEXT,
            updated_at        TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_players_team
            ON players(team_id);
        CREATE INDEX IF NOT EXISTS idx_players_nationality
            ON players(nationality);

        -- One row per player per match (summary fields).
        CREATE TABLE IF NOT EXISTS match_player_stats (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id          TEXT NOT NULL,
            player_id         TEXT NOT NULL,
            team_id           TEXT,
            team_side         TEXT,
            position          TEXT,
            is_goalkeeper     INTEGER DEFAULT 0,
            jersey_number     INTEGER,
            minutes_played    REAL,
            rating            REAL,
            rating_display    TEXT,
            in_base_lineup    INTEGER,
            updated_at        TEXT,
            UNIQUE(match_id, player_id),
            FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_match_player_stats_match
            ON match_player_stats(match_id);
        CREATE INDEX IF NOT EXISTS idx_match_player_stats_player
            ON match_player_stats(player_id);

        -- Flexible per-match stat values (handles new/missing stat types).
        CREATE TABLE IF NOT EXISTS match_stat_values (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            match_player_stats_id INTEGER NOT NULL,
            stat_key              TEXT NOT NULL,
            numeric_value         REAL,
            display_value         TEXT,
            value                 TEXT,
            UNIQUE(match_player_stats_id, stat_key),
            FOREIGN KEY (match_player_stats_id)
                REFERENCES match_player_stats(id) ON DELETE CASCADE,
            FOREIGN KEY (stat_key) REFERENCES stat_types(stat_key)
        );

        CREATE INDEX IF NOT EXISTS idx_match_stat_values_key
            ON match_stat_values(stat_key);

        -- One row per goalkeeper per match.
        CREATE TABLE IF NOT EXISTS goalkeeper_match_stats (
            id                            INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id                      TEXT NOT NULL,
            player_id                     TEXT NOT NULL,
            team_id                       TEXT,
            minutes_played                REAL,
            rating                        REAL,
            saves_total                   REAL,
            goals_conceded                REAL,
            goals_prevented               REAL,
            expected_goals_on_target_faced REAL,
            keeper_sweeper_total          REAL,
            keeper_throws_total           REAL,
            punches_total                 REAL,
            clean_sheet                   INTEGER DEFAULT 0,
            updated_at                    TEXT,
            UNIQUE(match_id, player_id),
            FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_goalkeeper_match_stats_match
            ON goalkeeper_match_stats(match_id);
        CREATE INDEX IF NOT EXISTS idx_goalkeeper_match_stats_player
            ON goalkeeper_match_stats(player_id);

        CREATE TABLE IF NOT EXISTS goalkeeper_stat_values (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            goalkeeper_match_stats_id INTEGER NOT NULL,
            stat_key                  TEXT NOT NULL,
            numeric_value             REAL,
            display_value             TEXT,
            value                     TEXT,
            UNIQUE(goalkeeper_match_stats_id, stat_key),
            FOREIGN KEY (goalkeeper_match_stats_id)
                REFERENCES goalkeeper_match_stats(id) ON DELETE CASCADE
        );

        -- Tournament cumulative stats (one header row per player).
        CREATE TABLE IF NOT EXISTS tournament_player_stats (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id   TEXT NOT NULL,
            player_id       TEXT NOT NULL,
            team_id         TEXT,
            matches_played  INTEGER DEFAULT 0,
            minutes_played  REAL DEFAULT 0,
            avg_rating      REAL,
            updated_at      TEXT,
            UNIQUE(tournament_id, player_id),
            FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id)
        );

        CREATE INDEX IF NOT EXISTS idx_tournament_player_stats_player
            ON tournament_player_stats(player_id);

        CREATE TABLE IF NOT EXISTS tournament_stat_values (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_player_stats_id INTEGER NOT NULL,
            stat_key                  TEXT NOT NULL,
            numeric_value             REAL,
            display_value             TEXT,
            value                     TEXT,
            UNIQUE(tournament_player_stats_id, stat_key),
            FOREIGN KEY (tournament_player_stats_id)
                REFERENCES tournament_player_stats(id) ON DELETE CASCADE,
            FOREIGN KEY (stat_key) REFERENCES stat_types(stat_key)
        );

        CREATE INDEX IF NOT EXISTS idx_tournament_stat_values_key
            ON tournament_stat_values(stat_key);

        CREATE TABLE IF NOT EXISTS awards (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id       TEXT NOT NULL,
            award_type      TEXT NOT NULL,
            match_id        TEXT,
            tournament_id   TEXT,
            value           REAL,
            value_text      TEXT,
            awarded_at      TEXT,
            notes           TEXT,
            UNIQUE(player_id, award_type, match_id, tournament_id),
            FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_awards_player
            ON awards(player_id);
        CREATE INDEX IF NOT EXISTS idx_awards_type
            ON awards(award_type);
        CREATE INDEX IF NOT EXISTS idx_awards_match
            ON awards(match_id);

        -- Cross-referenced against worldcup.db's real fixture list so match-level
        -- queries can exclude qualifiers/other competitions synced under the same
        -- SportDB tournament id. Populated by sync3.tag_world_cup_matches().
        CREATE TABLE IF NOT EXISTS match_world_cup_flag (
            match_id      TEXT PRIMARY KEY,
            is_world_cup  INTEGER NOT NULL DEFAULT 0,
            home_team     TEXT,
            away_team     TEXT,
            date          TEXT,
            stage         TEXT,
            home_score    INTEGER,
            away_score    INTEGER,
            updated_at    TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_match_world_cup_flag_is_wc
            ON match_world_cup_flag(is_world_cup);

        CREATE TABLE IF NOT EXISTS sync_log (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_type           TEXT,
            started_at          TEXT,
            completed_at        TEXT,
            records_processed   INTEGER,
            status              TEXT,
            error_message       TEXT
        );

        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        );
        """
    )

    cur.execute("SELECT COUNT(*) FROM schema_version")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    else:
        cur.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))

    cur.executemany(
        """
        INSERT OR IGNORE INTO stat_types (stat_key, label, category)
        VALUES (?, ?, ?)
        """,
        STAT_TYPE_SEED,
    )

    cur.execute(
        """
        INSERT OR IGNORE INTO tournaments (tournament_id, name, season, slug, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (TOURNAMENT_ID, TOURNAMENT_NAME, TOURNAMENT_SEASON, TOURNAMENT_ID, utc_now()),
    )

    conn.commit()
    conn.close()
    print("Player stats DB initialized.")


def ensure_stat_type(cur: sqlite3.Cursor, stat_key: str, label: str | None = None) -> None:
    """Register unknown stat keys discovered at runtime."""
    cur.execute(
        """
        INSERT OR IGNORE INTO stat_types (stat_key, label, category)
        VALUES (?, ?, 'unknown')
        """,
        (stat_key, label or stat_key),
    )


if __name__ == "__main__":
    init_db()
