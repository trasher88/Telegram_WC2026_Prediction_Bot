import aiosqlite

from db import DB_PATH


async def get_player_recent_finished_predictions(
    user_id: int,
    limit: int = 10
):
    async with aiosqlite.connect(DB_PATH) as db:
        return await (
            await db.execute(
                """
                SELECT
                    m.id,
                    m.home_team,
                    m.away_team,
                    m.start_time,
                    m.home_score,
                    m.away_score,
                    p.home_score_pred,
                    p.away_score_pred
                FROM predictions p
                JOIN matches m
                    ON m.id = p.match_id
                WHERE p.user_id = ?
                  AND m.status = 'finished'
                  AND m.home_score IS NOT NULL
                  AND m.away_score IS NOT NULL
                ORDER BY m.start_time DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
        ).fetchall()


async def get_player_all_finished_predictions(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        return await (
            await db.execute(
                """
                SELECT
                    m.id,
                    m.home_team,
                    m.away_team,
                    m.start_time,
                    m.home_score,
                    m.away_score,
                    p.home_score_pred,
                    p.away_score_pred
                FROM predictions p
                JOIN matches m
                    ON m.id = p.match_id
                WHERE p.user_id = ?
                  AND m.status = 'finished'
                  AND m.home_score IS NOT NULL
                  AND m.away_score IS NOT NULL
                ORDER BY m.start_time DESC
                """,
                (user_id,),
            )
        ).fetchall()


async def get_player_total_predictions_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await (
            await db.execute(
                """
                SELECT COUNT(*)
                FROM predictions
                WHERE user_id = ?
                """,
                (user_id,),
            )
        ).fetchone()

    return row[0] if row else 0


async def get_player_open_predictions_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await (
            await db.execute(
                """
                SELECT COUNT(*)
                FROM predictions p
                JOIN matches m
                    ON m.id = p.match_id
                WHERE p.user_id = ?
                  AND m.status != 'finished'
                """,
                (user_id,),
            )
        ).fetchone()

    return row[0] if row else 0