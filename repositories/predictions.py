import aiosqlite

from db import DB_PATH


async def get_predicted_match_ids(user_id: int) -> set[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await (
            await db.execute(
                """
                SELECT match_id
                FROM predictions
                WHERE user_id=?
                """,
                (user_id,),
            )
        ).fetchall()

    return {row[0] for row in rows}


async def get_user_predictions(
    user_id: int,
    stage: str | None = None,
    matchday: int | None = None,
):
    query = """
        SELECT
            m.home_team,
            m.away_team,
            m.home_score,
            m.away_score,
            p.home_score_pred,
            p.away_score_pred,
            m.status,
            m.start_time
        FROM predictions p
        JOIN matches m
            ON p.match_id = m.id
        WHERE p.user_id = ?
    """

    params: list[object] = [user_id]

    if matchday is not None:
        query += """
            AND m.stage = 'GROUP_STAGE'
            AND m.matchday = ?
        """
        params.append(matchday)

    elif stage is not None:
        query += """
            AND m.stage = ?
        """
        params.append(stage)

    query += """
        ORDER BY m.start_time
    """

    async with aiosqlite.connect(DB_PATH) as db:
        return await (await db.execute(query, params)).fetchall()


async def count_predictions_for_match(match_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await (
            await db.execute(
                """
                SELECT COUNT(*)
                FROM predictions
                WHERE match_id=?
                """,
                (match_id,),
            )
        ).fetchone()

    return row[0]
