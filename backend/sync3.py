"""
Ingest player profiles and statistics from SportDB.dev into worldcup_stats.db.

API docs: https://dashboard.sportdb.dev/docs
Base URL: https://api.sportdb.dev

This script reads match results and player stats from SportDB and writes to
worldcup_stats.db. It does not modify worldcup.db.
"""

from __future__ import annotations

import os
import sqlite3
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

try:
    from .db3 import (
        BASE_DIR,
        GOALKEEPER_STAT_KEYS,
        TOURNAMENT_ID,
        TOURNAMENT_NAME,
        ensure_stat_type,
        get_conn,
        init_db,
        utc_now,
    )
except ImportError:
    from db3 import (
        BASE_DIR,
        GOALKEEPER_STAT_KEYS,
        TOURNAMENT_ID,
        TOURNAMENT_NAME,
        ensure_stat_type,
        get_conn,
        init_db,
        utc_now,
    )

load_dotenv(Path(__file__).resolve().parent / ".env")

API_KEY = os.getenv("FOOTBALL_KEY")
BASE_URL = "https://api.sportdb.dev"
HEADERS = {"X-API-Key": API_KEY}

RESULTS_ENDPOINT = (
    "/api/flashscore/football/world:8/world-championship:lvUBR5F8/2026/results"
)

# Pacing/backoff for a rate-limited API — cheap insurance against losing another key.
REQUEST_DELAY_SECONDS = 0.4
RATE_LIMIT_MAX_RETRIES = 3


class RateLimited(Exception):
    """Raised when the API keeps returning 429 after retrying with backoff."""


class QuotaExceeded(RateLimited):
    """Raised on 402 Payment Required — the plan's quota is exhausted; retrying won't help."""


# SportDB's results endpoint returns every completed match under the same
# tournament id, including qualifiers — these map Flashscore's team names to
# worldcup.db's (Zafronix) team names where they differ, so matches can be
# cross-referenced against the real 48-team fixture list.
TEAM_NAME_ALIASES = {
    "D.R. Congo": "DR Congo",
    "South Korea": "Korea Republic",
    "Czech Republic": "Czechia",
    "Turkey": "Türkiye",
    "Cape Verde": "Cabo Verde",
    "Iran": "IR Iran",
    "Ivory Coast": "Côte d'Ivoire",
    "United States": "USA",
}


# Map SportDB bonusTypes to normalized award codes.
BONUS_AWARD_MAP = {
    "GOALS": "MATCH_GOALS",
    "ASSISTS": "MATCH_ASSISTS",
    "CLEAN_SHEET": "CLEAN_SHEET",
    "WINNING_GOAL": "WINNING_GOAL",
    "BIG_CHANCES_CREATED": "BIG_CHANCES_CREATED",
    "BIG_CHANCES_MISSED": "BIG_CHANCES_MISSED",
    "BIG_CHANCES_SAVED": "BIG_CHANCES_SAVED",
    "SHOT_STOPPING": "SHOT_STOPPING",
    "RED_CARDS": "RED_CARD",
    "ERRORS_LEADING_TO_GOAL": "ERROR_LEADING_TO_GOAL",
    "ERRORS_LEADING_TO_SHOT": "ERROR_LEADING_TO_SHOT",
    "SHOOTOUT_PENALTIES_SCORED": "SHOOTOUT_PENALTY_SCORED",
    "SHOOTOUT_PENALTIES_MISSED": "SHOOTOUT_PENALTY_MISSED",
    "SHOOTOUT_PENALTIES_SAVED": "SHOOTOUT_PENALTY_SAVED",
}


def get_json(path: str) -> dict | list:
    for attempt in range(RATE_LIMIT_MAX_RETRIES):
        response = requests.get(BASE_URL + path, headers=HEADERS, timeout=30)
        if response.status_code == 402:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = None
            raise QuotaExceeded(detail or f"402 Payment Required on {path}")
        if response.status_code == 429:
            if attempt == RATE_LIMIT_MAX_RETRIES - 1:
                raise RateLimited(f"429 on {path} after {RATE_LIMIT_MAX_RETRIES} attempts")
            wait = float(response.headers.get("Retry-After", 2 ** (attempt + 1)))
            print(f"  429 rate limited on {path}, waiting {wait:.0f}s "
                  f"(attempt {attempt + 1}/{RATE_LIMIT_MAX_RETRIES}) ...")
            time.sleep(wait)
            continue
        response.raise_for_status()
        time.sleep(REQUEST_DELAY_SECONDS)
        return response.json()
    raise RateLimited(f"429 on {path} after {RATE_LIMIT_MAX_RETRIES} attempts")


def calc_age(dob: str | None) -> int | None:
    if not dob:
        return None
    try:
        born = datetime.strptime(dob[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def get_completed_matches() -> list[dict]:
    matches: list[dict] = []
    page = 1
    while True:
        data = get_json(f"{RESULTS_ENDPOINT}?page={page}")
        if not data:
            break
        matches.extend(data)
        if len(data) < 100:
            break
        page += 1
    return matches


def get_synced_match_ids(cur: sqlite3.Cursor) -> set[str]:
    cur.execute("SELECT DISTINCT match_id FROM match_player_stats")
    return {row[0] for row in cur.fetchall()}


def parse_lineup_jerseys(lineups: list[dict]) -> dict[str, int]:
    """Return {player_id: jersey_number} from match lineups."""
    jerseys: dict[str, int] = {}
    for group in lineups or []:
        for side in ("home", "away"):
            for player in group.get(side) or []:
                player_id = player.get("participantId")
                number = player.get("participantNumber")
                if player_id and number is not None:
                    try:
                        jerseys[player_id] = int(number)
                    except (TypeError, ValueError):
                        pass
    return jerseys


def build_team_lookup(playerstats: dict) -> dict[str, dict]:
    return {team["id"]: team for team in playerstats.get("teams") or []}


def fetch_player_profile(link: str | None) -> dict | None:
    if not link:
        return None
    try:
        return get_json(link)
    except requests.HTTPError:
        return None


def upsert_player(
    cur: sqlite3.Cursor,
    player: dict,
    team_lookup: dict[str, dict],
    jersey_number: int | None,
    profile: dict | None,
) -> None:
    """Insert or update a player profile, merging match and profile API data."""
    player_id = player.get("id")
    if not player_id:
        return

    team_id = player.get("teamId")
    team = team_lookup.get(team_id, {})
    position = (player.get("position") or {}).get("name")
    is_gk = 1 if (player.get("position") or {}).get("isGoalkeeper") else 0
    image = (player.get("images") or [None])[0]

    nationality = None
    nationality_id = None
    country = player.get("country") or {}
    if country.get("name"):
        nationality = country.get("name")
    if country.get("id") is not None:
        nationality_id = str(country.get("id"))

    first_name = last_name = dob = club_name = club_id = None
    market_value = player_status = preferred_foot = None
    height = weight = None

    if profile:
        first_name = profile.get("firstName")
        last_name = profile.get("lastName")
        dob = profile.get("dob")
        club_name = profile.get("teamName")
        club_id = profile.get("teamId")
        market_value = profile.get("marketValue")
        player_status = profile.get("playerStatus")
        if profile.get("photo"):
            image = profile.get("photo")
        if profile.get("countryName"):
            nationality = profile.get("countryName")
        if profile.get("countryId"):
            nationality_id = str(profile.get("countryId"))
        if profile.get("position"):
            position = profile.get("position") or position

    full_name = player.get("name")
    if first_name and last_name and not full_name:
        full_name = f"{first_name} {last_name}".strip()

    cur.execute(
        """
        INSERT INTO players (
            player_id, full_name, display_name, first_name, last_name, slug,
            nationality, nationality_id, team_id, team_name, jersey_number,
            position, is_goalkeeper, date_of_birth, age, height, weight,
            preferred_foot, club_name, club_id, image_url, profile_link,
            market_value, player_status, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_id) DO UPDATE SET
            full_name       = COALESCE(excluded.full_name, players.full_name),
            display_name    = COALESCE(excluded.display_name, players.display_name),
            first_name      = COALESCE(excluded.first_name, players.first_name),
            last_name       = COALESCE(excluded.last_name, players.last_name),
            slug            = COALESCE(excluded.slug, players.slug),
            nationality     = COALESCE(excluded.nationality, players.nationality),
            nationality_id  = COALESCE(excluded.nationality_id, players.nationality_id),
            team_id         = COALESCE(excluded.team_id, players.team_id),
            team_name       = COALESCE(excluded.team_name, players.team_name),
            jersey_number   = COALESCE(excluded.jersey_number, players.jersey_number),
            position        = COALESCE(excluded.position, players.position),
            is_goalkeeper   = excluded.is_goalkeeper,
            date_of_birth   = COALESCE(excluded.date_of_birth, players.date_of_birth),
            age             = COALESCE(excluded.age, players.age),
            height          = COALESCE(excluded.height, players.height),
            weight          = COALESCE(excluded.weight, players.weight),
            preferred_foot  = COALESCE(excluded.preferred_foot, players.preferred_foot),
            club_name       = COALESCE(excluded.club_name, players.club_name),
            club_id         = COALESCE(excluded.club_id, players.club_id),
            image_url       = COALESCE(excluded.image_url, players.image_url),
            profile_link    = COALESCE(excluded.profile_link, players.profile_link),
            market_value    = COALESCE(excluded.market_value, players.market_value),
            player_status   = COALESCE(excluded.player_status, players.player_status),
            updated_at      = excluded.updated_at
        """,
        (
            player_id,
            full_name,
            player.get("shortName"),
            first_name,
            last_name,
            player.get("slug"),
            nationality,
            nationality_id,
            team_id,
            team.get("name"),
            jersey_number,
            position,
            is_gk,
            dob,
            calc_age(dob),
            height,
            weight,
            preferred_foot,
            club_name,
            club_id,
            image,
            player.get("link"),
            market_value,
            player_status,
            utc_now(),
        ),
    )


def upsert_match_player_stats(
    cur: sqlite3.Cursor,
    match_id: str,
    player: dict,
    stats_by_player: dict[str, list[dict]],
    jersey_number: int | None,
) -> int:
    """Upsert the one-row-per-player-per-match summary and return its row id."""
    player_id = player["id"]
    position = (player.get("position") or {}).get("name")
    is_gk = 1 if (player.get("position") or {}).get("isGoalkeeper") else 0
    rating_obj = player.get("rating") or {}
    rating = rating_obj.get("numericValue")
    rating_display = rating_obj.get("value")

    player_stats = stats_by_player.get(player_id, [])
    minutes = None
    for stat in player_stats:
        if stat.get("statsKey") == "matchMinutesPlayed":
            minutes = stat.get("numericValue")
            break

    cur.execute(
        """
        INSERT INTO match_player_stats (
            match_id, player_id, team_id, team_side, position, is_goalkeeper,
            jersey_number, minutes_played, rating, rating_display,
            in_base_lineup, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(match_id, player_id) DO UPDATE SET
            team_id         = excluded.team_id,
            team_side       = excluded.team_side,
            position        = excluded.position,
            is_goalkeeper   = excluded.is_goalkeeper,
            jersey_number   = COALESCE(excluded.jersey_number, match_player_stats.jersey_number),
            minutes_played  = excluded.minutes_played,
            rating          = excluded.rating,
            rating_display  = excluded.rating_display,
            in_base_lineup  = excluded.in_base_lineup,
            updated_at      = excluded.updated_at
        """,
        (
            match_id,
            player_id,
            player.get("teamId"),
            player.get("teamSide"),
            position,
            is_gk,
            jersey_number,
            minutes,
            rating,
            rating_display,
            1 if player.get("inBaseLineup") else 0,
            utc_now(),
        ),
    )
    cur.execute(
        "SELECT id FROM match_player_stats WHERE match_id = ? AND player_id = ?",
        (match_id, player_id),
    )
    row = cur.fetchone()
    return int(row["id"])


def upsert_match_stat_values(
    cur: sqlite3.Cursor,
    match_player_stats_id: int,
    player_stats: list[dict],
) -> None:
    for stat in player_stats:
        stat_key = stat.get("statsKey")
        if not stat_key:
            continue
        ensure_stat_type(cur, stat_key)
        cur.execute(
            """
            INSERT INTO match_stat_values (
                match_player_stats_id, stat_key, numeric_value, display_value, value
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(match_player_stats_id, stat_key) DO UPDATE SET
                numeric_value = excluded.numeric_value,
                display_value = excluded.display_value,
                value         = excluded.value
            """,
            (
                match_player_stats_id,
                stat_key,
                stat.get("numericValue"),
                stat.get("displayValue"),
                stat.get("value"),
            ),
        )


def upsert_goalkeeper_match_stats(
    cur: sqlite3.Cursor,
    match_id: str,
    player: dict,
    player_stats: list[dict],
    bonus_types: list[str] | None,
) -> None:
    player_id = player["id"]
    stat_map = {s["statsKey"]: s for s in player_stats if s.get("statsKey")}

    def stat_value(key: str) -> float | None:
        return stat_map.get(key, {}).get("numericValue")

    rating_obj = player.get("rating") or {}
    clean_sheet = 1 if bonus_types and "CLEAN_SHEET" in bonus_types else 0

    cur.execute(
        """
        INSERT INTO goalkeeper_match_stats (
            match_id, player_id, team_id, minutes_played, rating,
            saves_total, goals_conceded, goals_prevented,
            expected_goals_on_target_faced, keeper_sweeper_total,
            keeper_throws_total, punches_total, clean_sheet, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(match_id, player_id) DO UPDATE SET
            team_id                        = excluded.team_id,
            minutes_played                 = excluded.minutes_played,
            rating                         = excluded.rating,
            saves_total                    = excluded.saves_total,
            goals_conceded                 = excluded.goals_conceded,
            goals_prevented                = excluded.goals_prevented,
            expected_goals_on_target_faced = excluded.expected_goals_on_target_faced,
            keeper_sweeper_total           = excluded.keeper_sweeper_total,
            keeper_throws_total            = excluded.keeper_throws_total,
            punches_total                  = excluded.punches_total,
            clean_sheet                    = excluded.clean_sheet,
            updated_at                     = excluded.updated_at
        """,
        (
            match_id,
            player_id,
            player.get("teamId"),
            stat_value("matchMinutesPlayed"),
            rating_obj.get("numericValue"),
            stat_value("savesTotal"),
            stat_value("goalsConceded"),
            stat_value("goalsPrevented"),
            stat_value("expectedGoalsOnTargetFaced"),
            stat_value("keeperSweeperTotal"),
            stat_value("keeperThrowsTotal"),
            stat_value("punchesTotal"),
            clean_sheet,
            utc_now(),
        ),
    )

    cur.execute(
        "SELECT id FROM goalkeeper_match_stats WHERE match_id = ? AND player_id = ?",
        (match_id, player_id),
    )
    gk_row = cur.fetchone()
    if not gk_row:
        return

    gk_id = int(gk_row["id"])
    for stat in player_stats:
        stat_key = stat.get("statsKey")
        if stat_key not in GOALKEEPER_STAT_KEYS:
            continue
        cur.execute(
            """
            INSERT INTO goalkeeper_stat_values (
                goalkeeper_match_stats_id, stat_key, numeric_value, display_value, value
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(goalkeeper_match_stats_id, stat_key) DO UPDATE SET
                numeric_value = excluded.numeric_value,
                display_value = excluded.display_value,
                value         = excluded.value
            """,
            (
                gk_id,
                stat_key,
                stat.get("numericValue"),
                stat.get("displayValue"),
                stat.get("value"),
            ),
        )


def upsert_award(
    cur: sqlite3.Cursor,
    player_id: str,
    award_type: str,
    match_id: str | None = None,
    tournament_id: str | None = TOURNAMENT_ID,
    value: float | None = None,
    value_text: str | None = None,
    notes: str | None = None,
) -> None:
    cur.execute(
        """
        INSERT INTO awards (
            player_id, award_type, match_id, tournament_id,
            value, value_text, awarded_at, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_id, award_type, match_id, tournament_id) DO UPDATE SET
            value      = COALESCE(excluded.value, awards.value),
            value_text = COALESCE(excluded.value_text, awards.value_text),
            awarded_at = excluded.awarded_at,
            notes      = COALESCE(excluded.notes, awards.notes)
        """,
        (
            player_id,
            award_type,
            match_id,
            tournament_id,
            value,
            value_text,
            utc_now(),
            notes,
        ),
    )


def sync_match_awards(
    cur: sqlite3.Cursor,
    match_id: str,
    players: list[dict],
    stats_by_player: dict[str, list[dict]],
) -> None:
    for player in players:
        player_id = player.get("id")
        if not player_id:
            continue

        rating = player.get("rating") or {}
        if rating.get("isBestRating"):
            upsert_award(
                cur,
                player_id,
                "PLAYER_OF_MATCH",
                match_id=match_id,
                value=rating.get("numericValue"),
                value_text=rating.get("value"),
            )

        for bonus in player.get("bonusTypes") or []:
            award_type = BONUS_AWARD_MAP.get(bonus, bonus)
            value = None
            if bonus == "GOALS":
                value = _stat_numeric(stats_by_player, player_id, "goals")
            elif bonus == "ASSISTS":
                value = _stat_numeric(stats_by_player, player_id, "assistsGoal")
            upsert_award(cur, player_id, award_type, match_id=match_id, value=value)


def _stat_numeric(
    stats_by_player: dict[str, list[dict]], player_id: str, stat_key: str
) -> float | None:
    for stat in stats_by_player.get(player_id, []):
        if stat.get("statsKey") == stat_key:
            return stat.get("numericValue")
    return None


def group_stats_by_player(stats: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for stat in stats:
        player_id = stat.get("playerId")
        if player_id:
            grouped[player_id].append(stat)
    return grouped


def update_player_profile(cur: sqlite3.Cursor, player_id: str, profile: dict) -> None:
    """Patch bio fields onto an existing player row from a fetched profile payload."""
    first_name = profile.get("firstName")
    last_name = profile.get("lastName")
    dob = profile.get("dob")
    full_name = f"{first_name} {last_name}".strip() if first_name and last_name else None
    nationality_id = profile.get("countryId")

    cur.execute(
        """
        UPDATE players SET
            full_name      = COALESCE(?, full_name),
            first_name     = COALESCE(?, first_name),
            last_name      = COALESCE(?, last_name),
            date_of_birth  = COALESCE(?, date_of_birth),
            age            = COALESCE(?, age),
            club_name      = COALESCE(?, club_name),
            club_id        = COALESCE(?, club_id),
            market_value   = COALESCE(?, market_value),
            player_status  = COALESCE(?, player_status),
            nationality    = COALESCE(?, nationality),
            nationality_id = COALESCE(?, nationality_id),
            image_url      = COALESCE(?, image_url),
            position       = COALESCE(?, position),
            updated_at     = ?
        WHERE player_id = ?
        """,
        (
            full_name,
            first_name,
            last_name,
            dob,
            calc_age(dob),
            profile.get("teamName"),
            profile.get("teamId"),
            profile.get("marketValue"),
            profile.get("playerStatus"),
            profile.get("countryName"),
            str(nationality_id) if nationality_id is not None else None,
            profile.get("photo"),
            profile.get("position"),
            utc_now(),
            player_id,
        ),
    )


def sync_missing_profiles(cur: sqlite3.Cursor, conn: sqlite3.Connection) -> int:
    """
    Backfill bio data for players already in the DB whose profile hasn't been
    fetched yet, using the profile_link stored during the stats-only pass.
    Avoids re-fetching match playerstats/lineups entirely.
    """
    cur.execute(
        """
        SELECT player_id, profile_link FROM players
        WHERE profile_link IS NOT NULL
          AND date_of_birth IS NULL AND club_name IS NULL AND first_name IS NULL
        """
    )
    rows = cur.fetchall()
    print(f"Backfilling profiles for {len(rows)} players ...")

    updated = 0
    for index, row in enumerate(rows, 1):
        try:
            profile = fetch_player_profile(row["profile_link"])
        except RateLimited as exc:
            conn.commit()
            print(f"  rate limited after {updated}/{len(rows)} profiles: {exc}")
            print("  Rerun the profile backfill later — players already updated are skipped.")
            return updated

        if profile:
            update_player_profile(cur, row["player_id"], profile)
            updated += 1

        if index % 25 == 0:
            conn.commit()
            print(f"  [{index}/{len(rows)}] profiles fetched")

    conn.commit()
    return updated


def player_needs_profile(cur: sqlite3.Cursor, player_id: str) -> bool:
    cur.execute(
        """
        SELECT date_of_birth, club_name, first_name
        FROM players WHERE player_id = ?
        """,
        (player_id,),
    )
    row = cur.fetchone()
    if not row:
        return True
    return not (row["date_of_birth"] or row["club_name"] or row["first_name"])


def sync_match(
    cur: sqlite3.Cursor,
    match_id: str,
    fetch_profiles: bool = True,
) -> tuple[int, int]:
    """Sync one match. Returns (players_count, stats_count)."""
    playerstats = get_json(f"/api/flashscore/match/{match_id}/playerstats")
    if not playerstats:
        return 0, 0
    lineups = get_json(f"/api/flashscore/match/{match_id}/lineups")

    players = playerstats.get("players") or []
    stats = playerstats.get("stats") or []
    team_lookup = build_team_lookup(playerstats)
    jerseys = parse_lineup_jerseys(lineups)
    stats_by_player = group_stats_by_player(stats)

    profile_cache: dict[str, dict | None] = {}

    for player in players:
        player_id = player.get("id")
        if not player_id:
            continue

        profile = None
        if fetch_profiles and player_needs_profile(cur, player_id):
            link = player.get("link")
            if link not in profile_cache:
                profile_cache[link] = fetch_player_profile(link)
            profile = profile_cache[link]

        upsert_player(cur, player, team_lookup, jerseys.get(player_id), profile)

        mps_id = upsert_match_player_stats(
            cur, match_id, player, stats_by_player, jerseys.get(player_id)
        )
        upsert_match_stat_values(cur, mps_id, stats_by_player.get(player_id, []))

        if (player.get("position") or {}).get("isGoalkeeper"):
            upsert_goalkeeper_match_stats(
                cur,
                match_id,
                player,
                stats_by_player.get(player_id, []),
                player.get("bonusTypes"),
            )

    sync_match_awards(cur, match_id, players, stats_by_player)
    return len(players), len(stats)


def tag_world_cup_matches(cur: sqlite3.Cursor) -> tuple[int, int]:
    """
    Cross-reference every synced match_id against the real World Cup 2026
    fixture list in worldcup.db (by normalized team-pair) and persist the
    result in match_world_cup_flag. Purely local — no API calls. Safe to
    rerun any time; recomputes from scratch each call.

    Returns (tagged_as_world_cup, tagged_as_other).
    """
    wc_path = BASE_DIR / "worldcup.db"
    cur.execute("ATTACH DATABASE ? AS wc", (str(wc_path),))
    try:
        alias_values = ", ".join("(?, ?)" for _ in TEAM_NAME_ALIASES)
        alias_params = [v for pair in TEAM_NAME_ALIASES.items() for v in pair]

        cur.execute(
            f"""
            WITH alias(stats_name, wc_name) AS (VALUES {alias_values}),
            match_teams AS (
                SELECT mps.match_id,
                       MIN(p.team_name) AS team_a,
                       MAX(p.team_name) AS team_b
                FROM match_player_stats mps
                JOIN players p ON p.player_id = mps.player_id
                GROUP BY mps.match_id
                HAVING COUNT(DISTINCT p.team_name) = 2
            ),
            normalized AS (
                SELECT mt.match_id,
                       COALESCE(a1.wc_name, mt.team_a) AS team_a_wc,
                       COALESCE(a2.wc_name, mt.team_b) AS team_b_wc
                FROM match_teams mt
                LEFT JOIN alias a1 ON a1.stats_name = mt.team_a
                LEFT JOIN alias a2 ON a2.stats_name = mt.team_b
            )
            SELECT n.match_id, wcm.date, wcm.stage,
                   wcm.home_team, wcm.away_team,
                   wcm.home_score, wcm.away_score
            FROM normalized n
            JOIN wc.matches wcm
                ON (wcm.home_team = n.team_a_wc AND wcm.away_team = n.team_b_wc)
                OR (wcm.away_team = n.team_a_wc AND wcm.home_team = n.team_b_wc)
            """,
            alias_params,
        )
        matched = cur.fetchall()
        matched_ids = {row["match_id"] for row in matched}

        for row in matched:
            cur.execute(
                """
                INSERT INTO match_world_cup_flag (
                    match_id, is_world_cup, home_team, away_team,
                    date, stage, home_score, away_score, updated_at
                ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(match_id) DO UPDATE SET
                    is_world_cup = 1,
                    home_team    = excluded.home_team,
                    away_team    = excluded.away_team,
                    date         = excluded.date,
                    stage        = excluded.stage,
                    home_score   = excluded.home_score,
                    away_score   = excluded.away_score,
                    updated_at   = excluded.updated_at
                """,
                (
                    row["match_id"], row["home_team"], row["away_team"],
                    row["date"], row["stage"], row["home_score"], row["away_score"],
                    utc_now(),
                ),
            )

        cur.execute("SELECT DISTINCT match_id FROM match_player_stats")
        all_ids = {row[0] for row in cur.fetchall()}
        other_ids = all_ids - matched_ids

        for match_id in other_ids:
            cur.execute(
                """
                INSERT INTO match_world_cup_flag (match_id, is_world_cup, updated_at)
                VALUES (?, 0, ?)
                ON CONFLICT(match_id) DO UPDATE SET
                    is_world_cup = 0,
                    updated_at   = excluded.updated_at
                """,
                (match_id, utc_now()),
            )

        return len(matched_ids), len(other_ids)
    finally:
        cur.execute("DETACH DATABASE wc")


def rebuild_tournament_stats(cur: sqlite3.Cursor, tournament_id: str = TOURNAMENT_ID) -> None:
    """
    Recompute cumulative tournament statistics from match-level data.

    Sums additive numeric stats and averages rating across appearances.
    """
    cur.execute("DELETE FROM tournament_stat_values")
    cur.execute("DELETE FROM tournament_player_stats")

    cur.execute(
        """
        SELECT
            mps.player_id,
            mps.team_id,
            COUNT(DISTINCT mps.match_id) AS matches_played,
            SUM(COALESCE(mps.minutes_played, 0)) AS minutes_played,
            AVG(mps.rating) AS avg_rating
        FROM match_player_stats mps
        JOIN match_world_cup_flag mf ON mf.match_id = mps.match_id AND mf.is_world_cup = 1
        GROUP BY mps.player_id, mps.team_id
        """
    )

    player_rows = cur.fetchall()
    for row in player_rows:
        cur.execute(
            """
            INSERT INTO tournament_player_stats (
                tournament_id, player_id, team_id,
                matches_played, minutes_played, avg_rating, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tournament_id,
                row["player_id"],
                row["team_id"],
                row["matches_played"],
                row["minutes_played"],
                row["avg_rating"],
                utc_now(),
            ),
        )

    cur.execute(
        """
        SELECT
            mps.player_id,
            msv.stat_key,
            SUM(COALESCE(msv.numeric_value, 0)) AS total_value
        FROM match_player_stats mps
        JOIN match_world_cup_flag mf ON mf.match_id = mps.match_id AND mf.is_world_cup = 1
        JOIN match_stat_values msv ON msv.match_player_stats_id = mps.id
        WHERE msv.stat_key != 'fsRating'
          AND msv.stat_key NOT LIKE '%Efficiency'
          AND msv.stat_key NOT LIKE '%Accuracy'
        GROUP BY mps.player_id, msv.stat_key
        """
    )

    for row in cur.fetchall():
        cur.execute(
            """
            SELECT id FROM tournament_player_stats
            WHERE tournament_id = ? AND player_id = ?
            """,
            (tournament_id, row["player_id"]),
        )
        header = cur.fetchone()
        if not header:
            continue

        stat_key = row["stat_key"]
        ensure_stat_type(cur, stat_key)
        total = row["total_value"]
        cur.execute(
            """
            INSERT INTO tournament_stat_values (
                tournament_player_stats_id, stat_key,
                numeric_value, display_value, value
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                header["id"],
                stat_key,
                total,
                str(int(total)) if total == int(total) else str(round(total, 2)),
                str(total),
            ),
        )

    cur.execute(
        """
        SELECT mps.player_id, AVG(msv.numeric_value) AS avg_rating
        FROM match_player_stats mps
        JOIN match_world_cup_flag mf ON mf.match_id = mps.match_id AND mf.is_world_cup = 1
        JOIN match_stat_values msv ON msv.match_player_stats_id = mps.id
        WHERE msv.stat_key = 'fsRating'
        GROUP BY mps.player_id
        """
    )
    for row in cur.fetchall():
        cur.execute(
            """
            SELECT id FROM tournament_player_stats
            WHERE tournament_id = ? AND player_id = ?
            """,
            (tournament_id, row["player_id"]),
        )
        header = cur.fetchone()
        if not header:
            continue
        avg = row["avg_rating"]
        cur.execute(
            """
            INSERT INTO tournament_stat_values (
                tournament_player_stats_id, stat_key,
                numeric_value, display_value, value
            ) VALUES (?, 'fsRating', ?, ?, ?)
            ON CONFLICT(tournament_player_stats_id, stat_key) DO UPDATE SET
                numeric_value = excluded.numeric_value,
                display_value = excluded.display_value,
                value         = excluded.value
            """,
            (header["id"], avg, f"{avg:.1f}", f"{avg:.2f}"),
        )

    _rebuild_tournament_honours(cur, tournament_id)


def _rebuild_tournament_honours(cur: sqlite3.Cursor, tournament_id: str) -> None:
    """Derive tournament-level honours (e.g. Golden Boot leader) from aggregates."""
    cur.execute(
        """
        DELETE FROM awards
        WHERE tournament_id = ? AND match_id IS NULL
          AND award_type IN (
              'GOLDEN_BOOT_LEADER', 'GOLDEN_BALL_LEADER', 'MOST_PLAYER_OF_MATCH'
          )
        """,
        (tournament_id,),
    )

    cur.execute(
        """
        SELECT tps.player_id, tsv.numeric_value
        FROM tournament_player_stats tps
        JOIN tournament_stat_values tsv ON tsv.tournament_player_stats_id = tps.id
        WHERE tps.tournament_id = ? AND tsv.stat_key = 'goals'
        ORDER BY tsv.numeric_value DESC
        LIMIT 1
        """,
        (tournament_id,),
    )
    top_scorer = cur.fetchone()
    if top_scorer and top_scorer["numeric_value"]:
        upsert_award(
            cur,
            top_scorer["player_id"],
            "GOLDEN_BOOT_LEADER",
            match_id=None,
            tournament_id=tournament_id,
            value=top_scorer["numeric_value"],
            notes=f"Leading scorer in {TOURNAMENT_NAME}",
        )

    cur.execute(
        """
        SELECT tps.player_id, tsv.numeric_value
        FROM tournament_player_stats tps
        JOIN tournament_stat_values tsv ON tsv.tournament_player_stats_id = tps.id
        WHERE tps.tournament_id = ? AND tsv.stat_key = 'fsRating'
        ORDER BY tsv.numeric_value DESC
        LIMIT 1
        """,
        (tournament_id,),
    )
    top_rated = cur.fetchone()
    if top_rated and top_rated["numeric_value"]:
        upsert_award(
            cur,
            top_rated["player_id"],
            "GOLDEN_BALL_LEADER",
            match_id=None,
            tournament_id=tournament_id,
            value=top_rated["numeric_value"],
            notes=f"Highest average rating in {TOURNAMENT_NAME}",
        )

    cur.execute(
        """
        SELECT a.player_id, COUNT(*) AS potm_count
        FROM awards a
        JOIN match_world_cup_flag mf ON mf.match_id = a.match_id AND mf.is_world_cup = 1
        WHERE a.award_type = 'PLAYER_OF_MATCH' AND a.tournament_id = ?
        GROUP BY a.player_id
        ORDER BY potm_count DESC
        LIMIT 1
        """,
        (tournament_id,),
    )
    top_potm = cur.fetchone()
    if top_potm and top_potm["potm_count"]:
        upsert_award(
            cur,
            top_potm["player_id"],
            "MOST_PLAYER_OF_MATCH",
            match_id=None,
            tournament_id=tournament_id,
            value=float(top_potm["potm_count"]),
            notes="Most Player of the Match awards",
        )


def log_sync_start(cur: sqlite3.Cursor, sync_type: str) -> int:
    cur.execute(
        """
        INSERT INTO sync_log (sync_type, started_at, status)
        VALUES (?, ?, 'running')
        """,
        (sync_type, utc_now()),
    )
    return cur.lastrowid


def log_sync_complete(
    cur: sqlite3.Cursor,
    log_id: int,
    records: int,
    status: str = "success",
    error: str | None = None,
) -> None:
    cur.execute(
        """
        UPDATE sync_log
        SET completed_at = ?, records_processed = ?, status = ?, error_message = ?
        WHERE id = ?
        """,
        (utc_now(), records, status, error, log_id),
    )


def sync(fetch_profiles: bool = True, match_ids: list[str] | None = None) -> None:
    """
    Sync player stats from SportDB.dev into worldcup_stats.db.

    Args:
        fetch_profiles: When True, enrich players via /api/flashscore/player/{slug}/{id}.
        match_ids: Optional list of match IDs to sync; defaults to all completed results.
    """
    if not API_KEY:
        raise RuntimeError("FOOTBALL_KEY is not set in backend/.env")

    init_db()
    conn = get_conn()
    cur = conn.cursor()
    log_id = log_sync_start(cur, "full" if not match_ids else "partial")
    conn.commit()

    processed = 0
    try:
        if match_ids is None:
            matches = get_completed_matches()
            all_ids = [m["eventId"] for m in matches if m.get("eventId")]
            synced = get_synced_match_ids(cur)
            match_ids = [mid for mid in all_ids if mid not in synced]
            skipped = len(all_ids) - len(match_ids)
            if skipped:
                print(f"Skipping {skipped} already-synced matches; {len(match_ids)} remaining.")

        print(f"Syncing {len(match_ids)} matches from SportDB.dev ...")

        for index, match_id in enumerate(match_ids, 1):
            print(f"[{index}/{len(match_ids)}] {match_id}")
            try:
                players_count, stats_count = sync_match(cur, match_id, fetch_profiles)
                conn.commit()
                processed += 1
                print(f"  players: {players_count}, stat rows: {stats_count}")
            except RateLimited as exc:
                conn.rollback()
                print(f"  rate limited, stopping sync: {exc}")
                log_sync_complete(cur, log_id, processed, status="rate_limited", error=str(exc))
                conn.commit()
                print(f"Stopped after {processed}/{len(match_ids)} matches. "
                      "Rerun sync() later — already-synced matches are skipped automatically.")
                return
            except Exception as exc:
                conn.rollback()
                print(f"  failed: {exc}")

        print("Tagging World Cup matches vs. qualifiers/other competitions ...")
        tagged_wc, tagged_other = tag_world_cup_matches(cur)
        conn.commit()
        print(f"  {tagged_wc} World Cup matches, {tagged_other} other matches tagged")

        print("Rebuilding tournament aggregates ...")
        rebuild_tournament_stats(cur)
        conn.commit()
        log_sync_complete(cur, log_id, processed)
        conn.commit()
        print("Player stats sync complete.")
    except Exception as exc:
        conn.rollback()
        log_sync_complete(cur, log_id, processed, status="failed", error=str(exc))
        conn.commit()
        raise
    finally:
        conn.close()


def backfill_profiles() -> None:
    """Second pass: fetch bio profiles for players synced without them."""
    if not API_KEY:
        raise RuntimeError("FOOTBALL_KEY is not set in backend/.env")

    conn = get_conn()
    cur = conn.cursor()
    log_id = log_sync_start(cur, "profiles")
    conn.commit()

    try:
        updated = sync_missing_profiles(cur, conn)
        log_sync_complete(cur, log_id, updated)
        conn.commit()
        print(f"Profile backfill complete: {updated} players updated.")
    except Exception as exc:
        conn.rollback()
        log_sync_complete(cur, log_id, 0, status="failed", error=str(exc))
        conn.commit()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    # Pass 1: cheap (~2 requests/match), closes match/team/roster gaps first.
    sync(fetch_profiles=False)
    # Pass 2: backfill bios using profile_link already stored in pass 1 —
    # no need to re-fetch match data.
    backfill_profiles()
