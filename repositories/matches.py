import aiosqlite

from db import DB_PATH


async def get_matches_by_stage(stage: str):
    async with aiosqlite.connect(DB_PATH) as db:
        return await (
            await db.execute(
                """
                SELECT
                    home_team,
                    away_team,
                    start_time,
                    status,
                    home_score,
                    away_score
                FROM matches
                WHERE stage=?
                ORDER BY start_time
                """,
                (stage,),
            )
        ).fetchall()


async def get_group_matches_by_matchday(matchday: int):
    async with aiosqlite.connect(DB_PATH) as db:
        return await (
            await db.execute(
                """
                SELECT
                    home_team,
                    away_team,
                    start_time,
                    status,
                    home_score,
                    away_score
                FROM matches
                WHERE stage='GROUP_STAGE'
                AND matchday=?
                ORDER BY start_time
                """,
                (matchday,),
            )
        ).fetchall()


async def get_available_group_matches(matchday: int):
    async with aiosqlite.connect(DB_PATH) as db:
        return await (
            await db.execute(
                """
                SELECT id, home_team, away_team
                FROM matches
                WHERE stage='GROUP_STAGE'
                AND matchday=?
                AND status != 'finished'
                AND locked = 0
                AND TRIM(COALESCE(home_team, '')) != ''
                AND TRIM(COALESCE(away_team, '')) != ''
                AND LOWER(TRIM(home_team)) NOT IN ('unknown', 'tbd')
                AND LOWER(TRIM(away_team)) NOT IN ('unknown', 'tbd')
                ORDER BY start_time
                """,
                (matchday,),
            )
        ).fetchall()


async def get_available_stage_matches(stage: str):
    async with aiosqlite.connect(DB_PATH) as db:
        return await (
            await db.execute(
                """
                SELECT id, home_team, away_team
                FROM matches
                WHERE stage=?
                AND status != 'finished'
                AND locked = 0
                AND TRIM(COALESCE(home_team, '')) != ''
                AND TRIM(COALESCE(away_team, '')) != ''
                AND LOWER(TRIM(home_team)) NOT IN ('unknown', 'tbd')
                AND LOWER(TRIM(away_team)) NOT IN ('unknown', 'tbd')
                ORDER BY start_time
                """,
                (stage,),
            )
        ).fetchall()


async def set_match_score_finished(match_id: int, home: int, away: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE matches
            SET
                home_score=?,
                away_score=?,
                status='finished',
                locked = 1
            WHERE id=?
            """,
            (home, away, match_id),
        )
        await db.commit()


async def get_match_info(match_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        return await (
            await db.execute(
                """
                SELECT
                    home_team,
                    away_team,
                    status,
                    home_score,
                    away_score,
                    start_time
                FROM matches
                WHERE id=?
                """,
                (match_id,),
            )
        ).fetchone()


async def list_match_ids(limit: int = 30):
    async with aiosqlite.connect(DB_PATH) as db:
        return await (
            await db.execute(
                """
                SELECT
                    id,
                    home_team,
                    away_team,
                    start_time,
                    status,
                    stage,
                    matchday
                FROM matches
                ORDER BY start_time
                LIMIT ?
                """,
                (limit,),
            )
        ).fetchall()


async def lock_match(match_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE matches
            SET locked = 1
            WHERE id = ?
            """,
            (match_id,),
        )
        await db.commit()


async def list_match_ids_by_stage(stage: str):
    async with aiosqlite.connect(DB_PATH) as db:
        return await (
            await db.execute(
                """
                SELECT
                    id,
                    home_team,
                    away_team,
                    start_time,
                    status,
                    stage,
                    matchday
                FROM matches
                WHERE stage = ?
                ORDER BY start_time
                """,
                (stage,),
            )
        ).fetchall()


async def list_match_ids_by_group_round(matchday: int):
    async with aiosqlite.connect(DB_PATH) as db:
        return await (
            await db.execute(
                """
                SELECT
                    id,
                    home_team,
                    away_team,
                    start_time,
                    status,
                    stage,
                    matchday
                FROM matches
                WHERE stage = 'GROUP_STAGE'
                  AND matchday = ?
                ORDER BY start_time
                """,
                (matchday,),
            )
        ).fetchall()