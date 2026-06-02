import aiosqlite

from db import DB_PATH


async def is_match_processed(match_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await (
            await db.execute(
                """
                SELECT 1
                FROM processed_matches
                WHERE match_id=?
                """,
                (match_id,),
            )
        ).fetchone()

    return row is not None


async def get_users_dashboard_data():
    async with aiosqlite.connect(DB_PATH) as db:
        total = await (await db.execute("SELECT COUNT(*) FROM users")).fetchone()

        active = await (
            await db.execute(
                """
                SELECT COUNT(DISTINCT user_id)
                FROM predictions
                """
            )
        ).fetchone()

        top = await (
            await db.execute(
                """
                SELECT
                    u.id,
                    u.display_name,
                    u.username,
                    u.first_name,
                    COUNT(p.match_id) as preds
                FROM users u
                LEFT JOIN predictions p
                    ON u.id = p.user_id
                GROUP BY u.id
                ORDER BY preds DESC
                LIMIT 10
                """
            )
        ).fetchall()

    return {
        "total_users": total[0],
        "active_predictors": active[0],
        "top_activity": top,
    }


async def get_tournament_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        total_matches = await (await db.execute("SELECT COUNT(*) FROM matches")).fetchone()
        finished_matches = await (
            await db.execute("SELECT COUNT(*) FROM matches WHERE status='finished'")
        ).fetchone()
        live_matches = await (
            await db.execute("SELECT COUNT(*) FROM matches WHERE status='in_play'")
        ).fetchone()
        total_predictions = await (
            await db.execute("SELECT COUNT(*) FROM predictions")
        ).fetchone()
        total_users = await (await db.execute("SELECT COUNT(*) FROM users")).fetchone()
        active_users = await (
            await db.execute(
                """
                SELECT COUNT(DISTINCT user_id)
                FROM predictions
                """
            )
        ).fetchone()
        processed_matches = await (
            await db.execute("SELECT COUNT(*) FROM processed_matches")
        ).fetchone()

    return {
        "total_matches": total_matches[0],
        "finished_matches": finished_matches[0],
        "live_matches": live_matches[0],
        "total_predictions": total_predictions[0],
        "total_users": total_users[0],
        "active_users": active_users[0],
        "processed_matches": processed_matches[0],
    }
