import aiosqlite

from db import DB_PATH


LEADERBOARD_STATS_SQL = """
WITH user_stats AS (
    SELECT
        u.id,
        u.display_name,
        u.username,
        u.first_name,
        COALESCE(s.points, 0) AS points,
        COUNT(p.match_id) AS predictions_count,
        COALESCE(
            SUM(
                CASE
                    WHEN m.status = 'finished'
                     AND m.home_score IS NOT NULL
                     AND m.away_score IS NOT NULL
                     AND p.home_score_pred = m.home_score
                     AND p.away_score_pred = m.away_score
                    THEN 1
                    ELSE 0
                END
            ),
            0
        ) AS exact_scores
    FROM users u
    LEFT JOIN scores s
        ON u.id = s.user_id
    LEFT JOIN predictions p
        ON u.id = p.user_id
    LEFT JOIN matches m
        ON p.match_id = m.id
    WHERE u.is_approved = 1
    GROUP BY u.id
)
"""


async def get_leaderboard_data(limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        top_players = await (
            await db.execute(
                LEADERBOARD_STATS_SQL
                + """
                SELECT
                    id,
                    display_name,
                    username,
                    first_name,
                    points,
                    predictions_count,
                    exact_scores
                FROM user_stats
                ORDER BY
                    points DESC,
                    exact_scores DESC,
                    id ASC
                LIMIT ?
                """,
                (limit,),
            )
        ).fetchall()

        ranking = await (
            await db.execute(
                LEADERBOARD_STATS_SQL
                + """
                SELECT
                    id,
                    points,
                    exact_scores,
                    predictions_count
                FROM user_stats
                ORDER BY
                    points DESC,
                    exact_scores DESC,
                    id ASC
                """
            )
        ).fetchall()

    return top_players, ranking