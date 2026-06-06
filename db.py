import os
import aiosqlite
from config import ADMIN_IDS

DB_PATH = os.getenv("DB_PATH", "wc2026.db")


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                display_name TEXT,
                name_set INTEGER NOT NULL DEFAULT 0,
                is_approved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY,
                home_team TEXT,
                away_team TEXT,
                start_time TEXT,
                status TEXT,
                stage TEXT,
                matchday INTEGER,
                home_score INTEGER,
                away_score INTEGER,
                locked INTEGER NOT NULL DEFAULT 0,
                processed INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                user_id INTEGER NOT NULL,
                match_id INTEGER NOT NULL,
                home_score_pred INTEGER NOT NULL,
                away_score_pred INTEGER NOT NULL,
                PRIMARY KEY (user_id, match_id)
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS scores (
                user_id INTEGER PRIMARY KEY,
                points INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_matches (
                match_id INTEGER PRIMARY KEY,
                processed_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS match_notifications (
                match_id INTEGER NOT NULL,
                notification_type TEXT NOT NULL,
                sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (match_id, notification_type)
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_notifications (
                game_day TEXT NOT NULL,
                notification_type TEXT NOT NULL,
                sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (game_day, notification_type)
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS invite_codes (
                code TEXT PRIMARY KEY,
                created_by INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                used_by INTEGER,
                used_at TEXT,
                is_used INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_matches_stage_matchday
            ON matches(stage, matchday)
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_matches_start_time
            ON matches(start_time)
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_predictions_user_id
            ON predictions(user_id)
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_predictions_match_id
            ON predictions(match_id)
            """
        )

        # Админы всегда получают доступ автоматически
        for admin_id in ADMIN_IDS:
            await db.execute(
                """
                INSERT INTO users(
                    id,
                    is_approved
                )
                VALUES (?, 1)

                ON CONFLICT(id)
                DO UPDATE SET
                    is_approved = 1
                """,
                (admin_id,),
            )

            await db.execute(
                """
                INSERT OR IGNORE INTO scores(
                    user_id,
                    points
                )
                VALUES (?, 0)
                """,
                (admin_id,),
            )

        await db.commit()