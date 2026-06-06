from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from config import ADMIN_IDS
from repositories.invites import is_user_approved


class AccessMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)

        if not user:
            return await handler(event, data)

        if user.id in ADMIN_IDS:
            return await handler(event, data)

        if isinstance(event, Message):
            text = event.text or ""

            if text.startswith("/start"):
                return await handler(event, data)

        approved = await is_user_approved(user.id)

        if approved:
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer(
                "⛔ У тебя нет доступа к этому боту.\n\n"
                "Для участия нужна персональная ссылка-приглашение."
            )
            return

        if isinstance(event, CallbackQuery):
            await event.answer(
                "⛔ Нет доступа",
                show_alert=True,
            )
            return