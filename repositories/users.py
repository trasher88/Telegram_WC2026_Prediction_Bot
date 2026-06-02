import aiosqlite

from db import DB_PATH


async def ensure_user_registered(
    user_id: int,
    username: str | None,
    first_name: str | None,
) -> bool:
    """Create/update a Telegram user and return whether tournament name is set."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users(id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(id)
            DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                username,
                first_name,
            ),
        )

        await db.execute(
            """
            INSERT OR IGNORE INTO scores(user_id, points)
            VALUES (?, 0)
            """,
            (user_id,),
        )

        row = await (
            await db.execute(
                """
                SELECT display_name, name_set
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            )
        ).fetchone()

        await db.commit()

    if not row:
        return False

    display_name, name_set = row
    return bool(display_name and name_set)


async def set_user_display_name(user_id: int, display_name: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users
            SET
                display_name = ?,
                name_set = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (display_name, user_id),
        )

        await db.commit()


async def get_user_display_name(user_id: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await (
            await db.execute(
                """
                SELECT display_name
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            )
        ).fetchone()

    if not row:
        return None

    return row[0]


async def list_user_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await (await db.execute("SELECT id FROM users")).fetchall()

    return [row[0] for row in rows]
