import aiosqlite
from db import DB_PATH


def outcome(home: int, away: int) -> int:
    """
    1  = home win
    0  = draw
    -1 = away win
    """

    if home > away:
        return 1

    if home < away:
        return -1

    return 0


def calculate_points(pred_home: int, pred_away: int, real_home: int, real_away: int) -> int:
    """
    Scoring rules:
    - exact score: 2 points
    - correct outcome: 1 point
    - wrong outcome: 0 points
    """

    # Exact score
    if pred_home == real_home and pred_away == real_away:
        return 2

    # Correct winner / draw
    if outcome(pred_home, pred_away) == outcome(real_home, real_away):
        return 1

    return 0


async def process_finished_match(match_id: int):
    async with aiosqlite.connect(DB_PATH) as db:

        # CHECK IF ALREADY PROCESSED
        cur = await db.execute(
            """
            SELECT 1
            FROM processed_matches
            WHERE match_id=?
            """,
            (match_id,)
        )

        exists = await cur.fetchone()

        if exists:
            return

        # GET MATCH RESULT
        cur = await db.execute(
            """
            SELECT home_score, away_score, status
            FROM matches
            WHERE id=?
            """,
            (match_id,)
        )

        match = await cur.fetchone()

        if not match:
            return

        home_score, away_score, status = match

        if status != "finished":
            return

        if home_score is None or away_score is None:
            return

        # GET ALL PREDICTIONS
        cur = await db.execute(
            """
            SELECT user_id, home_score_pred, away_score_pred
            FROM predictions
            WHERE match_id=?
            """,
            (match_id,)
        )

        predictions = await cur.fetchall()

        # SCORING
        for user_id, ph, pa in predictions:

            points = calculate_points(ph, pa, home_score, away_score)

            await db.execute(
                """
                INSERT INTO scores(user_id, points)
                VALUES (?, ?)
                ON CONFLICT(user_id)
                DO UPDATE SET
                    points = points + excluded.points
                """,
                (user_id, points)
            )

        # MARK AS PROCESSED
        await db.execute(
            """
            INSERT INTO processed_matches(match_id)
            VALUES (?)
            """,
            (match_id,)
        )

        await db.commit()


async def rebuild_all_scores():
    async with aiosqlite.connect(DB_PATH) as db:

        # RESET SCORES
        await db.execute(
            """
            UPDATE scores
            SET points = 0
            """
        )

        # CLEAR PROCESSED
        await db.execute(
            """
            DELETE FROM processed_matches
            """
        )

        await db.commit()

    # GET FINISHED MATCHES
    async with aiosqlite.connect(DB_PATH) as db:

        cur = await db.execute(
            """
            SELECT id
            FROM matches
            WHERE status='finished'
            """
        )

        matches = await cur.fetchall()

    # REPROCESS
    for (match_id,) in matches:

        await process_finished_match(match_id)

    print("REBUILD COMPLETE")