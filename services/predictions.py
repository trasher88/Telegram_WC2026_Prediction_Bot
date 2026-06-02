from datetime import datetime, timedelta, timezone

import aiosqlite

from db import DB_PATH
from services.scoring import calculate_points
from utils import texts as T


UNKNOWN_TEAM_NAMES = {"unknown", "tbd", "неизвестная команда"}


def parse_match_time(start_time: str) -> datetime:
    if start_time.endswith("Z"):
        start_time = start_time.replace("Z", "+00:00")

    match_dt = datetime.fromisoformat(start_time)

    if match_dt.tzinfo is None:
        match_dt = match_dt.replace(tzinfo=timezone.utc)

    return match_dt


def is_unknown_team(team_name: str | None) -> bool:
    if not team_name:
        return True

    normalized = team_name.strip().lower()

    return normalized == "" or normalized in UNKNOWN_TEAM_NAMES


def has_unknown_teams(home_team: str | None, away_team: str | None) -> bool:
    return is_unknown_team(home_team) or is_unknown_team(away_team)


def unknown_teams_error_text() -> str:
    return (
        "⛔ Команды для этого матча ещё не определены.\n\n"
        "Прогноз пока недоступен."
    )


async def get_match_for_prediction(match_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT
                home_team,
                away_team,
                start_time,
                status,
                locked
            FROM matches
            WHERE id = ?
            """,
            (match_id,)
        )

        return await cur.fetchone()


async def check_prediction_allowed(match_id: int):
    match = await get_match_for_prediction(match_id)

    if not match:
        return False, T.MATCH_NOT_FOUND, None

    home_team, away_team, start_time, status, locked = match

    if has_unknown_teams(home_team, away_team):
        return (
            False,
            unknown_teams_error_text(),
            match
        )

    if locked == 1:
        return (
            False,
            f"🔒 Прогнозы уже закрыты\n\n"
            f"{home_team} — {away_team}",
            match
        )

    if status in [
        "finished",
        "in_play",
        "paused"
    ]:
        return (
            False,
            T.MATCH_ALREADY_STARTED_OR_END,
            match
        )

    match_dt = parse_match_time(start_time)
    now = datetime.now(timezone.utc)

    if now >= match_dt - timedelta(minutes=5):
        # Автоматически закрываем матч, даже если scheduler по какой-то причине не сработал.
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                UPDATE matches
                SET locked = 1
                WHERE id = ?
                """,
                (match_id,)
            )

            await db.commit()

        return (
            False,
            f"🔒 Прогнозы уже закрыты\n\n"
            f"{home_team} — {away_team}",
            match
        )

    return True, None, match


async def save_prediction_to_db(
    user_id: int,
    match_id: int,
    home_pred: int,
    away_pred: int
):
    """Atomically validate and save a prediction.

    The deadline/status/lock check and INSERT/UPDATE happen inside one
    transaction, so a prediction cannot slip in between lock and save.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")

        try:
            cur = await db.execute(
                """
                SELECT
                    home_team,
                    away_team,
                    start_time,
                    status,
                    locked
                FROM matches
                WHERE id = ?
                """,
                (match_id,)
            )

            match = await cur.fetchone()

            if not match:
                await db.rollback()
                return False, T.MATCH_NOT_FOUND, None

            home_team, away_team, start_time, status, locked = match

            if has_unknown_teams(home_team, away_team):
                await db.rollback()
                return (
                    False,
                    unknown_teams_error_text(),
                    match
                )

            if locked == 1:
                await db.rollback()
                return (
                    False,
                    f"🔒 Прогнозы уже закрыты\n\n"
                    f"{home_team} — {away_team}",
                    match
                )

            if status in ["finished", "in_play", "paused"]:
                await db.rollback()
                return False, T.MATCH_ALREADY_STARTED_OR_END, match

            match_dt = parse_match_time(start_time)
            now = datetime.now(timezone.utc)

            if now >= match_dt - timedelta(minutes=5):
                await db.execute(
                    """
                    UPDATE matches
                    SET locked = 1
                    WHERE id = ?
                    """,
                    (match_id,)
                )

                await db.commit()

                return (
                    False,
                    f"🔒 Прогнозы уже закрыты\n\n"
                    f"{home_team} — {away_team}",
                    match
                )

            await db.execute(
                """
                INSERT INTO predictions(
                    user_id,
                    match_id,
                    home_score_pred,
                    away_score_pred
                )
                VALUES (?, ?, ?, ?)

                ON CONFLICT(user_id, match_id)
                DO UPDATE SET
                    home_score_pred = excluded.home_score_pred,
                    away_score_pred = excluded.away_score_pred
                """,
                (
                    user_id,
                    match_id,
                    home_pred,
                    away_pred
                )
            )

            await db.commit()
            return True, None, match

        except Exception:
            await db.rollback()
            raise


def calculate_prediction_result(ph, pa, rh, ra, status):
    if status != "finished":
        return T.RESULT_SCHEDULED, 0

    if rh is None or ra is None:
        return T.RESULT_SCHEDULED, 0

    points = calculate_points(ph, pa, rh, ra)

    if points == 2:
        return T.RESULT_EXACT, 2

    if points == 1:
        return T.RESULT_OUTCOME, 1

    return T.RESULT_LOST, 0