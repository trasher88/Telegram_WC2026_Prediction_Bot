import secrets
import string
import aiosqlite
from db import DB_PATH

ALPHABET = string.ascii_uppercase + string.digits


def generate_invite_code(length: int = 8) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


async def create_invite_code(created_by: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        while True:
            code = generate_invite_code()

            try:
                await db.execute(
                    """
                    INSERT INTO invite_codes(code, created_by)
                    VALUES (?, ?)
                    """,
                    (code, created_by),
                )
                await db.commit()
                return code

            except aiosqlite.IntegrityError:
                continue


async def use_invite_code(code: str, user_id: int) -> bool:
    normalized_code = code.strip().upper()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")

        row = await (
            await db.execute(
                """
                SELECT is_used
                FROM invite_codes
                WHERE code = ?
                """,
                (normalized_code,),
            )
        ).fetchone()

        if not row:
            await db.rollback()
            return False

        if row[0] == 1:
            await db.rollback()
            return False

        await db.execute(
            """
            UPDATE invite_codes
            SET
                is_used = 1,
                used_by = ?,
                used_at = CURRENT_TIMESTAMP
            WHERE code = ?
            """,
            (user_id, normalized_code),
        )

        await db.execute(
            """
            UPDATE users
            SET is_approved = 1
            WHERE id = ?
            """,
            (user_id,),
        )

        await db.commit()
        return True


async def is_user_approved(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await (
            await db.execute(
                """
                SELECT is_approved
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            )
        ).fetchone()

    return bool(row and row[0] == 1)


async def approve_user(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users(id, is_approved)
            VALUES (?, 1)
            ON CONFLICT(id)
            DO UPDATE SET is_approved = 1
            """,
            (user_id,),
        )

        await db.execute(
            """
            INSERT OR IGNORE INTO scores(user_id, points)
            VALUES (?, 0)
            """,
            (user_id,),
        )

        await db.commit()


async def revoke_user(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users
            SET is_approved = 0
            WHERE id = ?
            """,
            (user_id,),
        )

        await db.commit()