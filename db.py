import os
import aiosqlite
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "wc2026.db"))


async def _ensure_column(db: aiosqlite.Connection, table: str, column: str, ddl: str) -> None:
    rows = await (await db.execute(f"PRAGMA table_info({table})")).fetchall()
    existing_columns = {row[1] for row in rows}

    if column not in existing_columns:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            display_name TEXT,
            name_set INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        );

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
            processed INTEGER DEFAULT 0,
            locked INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            match_id INTEGER,
            home_score_pred INTEGER,
            away_score_pred INTEGER,
            is_locked INTEGER DEFAULT 0,
            UNIQUE(user_id, match_id)
        );

        CREATE TABLE IF NOT EXISTS scores (
            user_id INTEGER PRIMARY KEY,
            points INTEGER DEFAULT 0
        );
        
        CREATE TABLE IF NOT EXISTS processed_matches (
            match_id INTEGER PRIMARY KEY
        );
        
        CREATE TABLE IF NOT EXISTS match_notifications (
            match_id INTEGER NOT NULL,
            notification_type TEXT NOT NULL,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (match_id, notification_type)
        );

        CREATE TABLE IF NOT EXISTS daily_notifications (
            game_day TEXT NOT NULL,
            notification_type TEXT NOT NULL,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (game_day, notification_type)
        );

        CREATE INDEX IF NOT EXISTS idx_predictions_user_id
        ON predictions(user_id);

        CREATE INDEX IF NOT EXISTS idx_predictions_match_id
        ON predictions(match_id);

        CREATE INDEX IF NOT EXISTS idx_matches_stage_matchday_start
        ON matches(stage, matchday, start_time);

        CREATE INDEX IF NOT EXISTS idx_matches_status
        ON matches(status);

        CREATE INDEX IF NOT EXISTS idx_matches_locked_start
        ON matches(locked, start_time);

        CREATE INDEX IF NOT EXISTS idx_matches_start_time
        ON matches(start_time);
        """)

        # Existing installations may already have the old users table.
        await _ensure_column(db, "users", "display_name", "display_name TEXT")
        await _ensure_column(db, "users", "name_set", "name_set INTEGER NOT NULL DEFAULT 0")
        await _ensure_column(db, "users", "created_at", "created_at TEXT")
        await _ensure_column(db, "users", "updated_at", "updated_at TEXT")

        await db.commit()
