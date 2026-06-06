import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from config import TOKEN, ENABLE_API_SYNC, TELEGRAM_API_BASE_URL
from db import init_db
from handlers.leaderboard import router as lb_router
from handlers.player_stats import router as player_stats_router
from handlers.user import router as user_router
from scheduler import setup_scheduler, sync_matches

from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from middleware.access import AccessMiddleware

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    if TELEGRAM_API_BASE_URL:
        session = AiohttpSession(
            api=TelegramAPIServer.from_base(TELEGRAM_API_BASE_URL)
        )
        bot = Bot(token=TOKEN, session=session)
    else:
        bot = Bot(token=TOKEN)

    dp = Dispatcher()

    dp.message.middleware(AccessMiddleware())
    dp.callback_query.middleware(AccessMiddleware())

    dp.include_router(user_router)
    dp.include_router(lb_router)
    dp.include_router(player_stats_router)

    await init_db()

    me = await bot.get_me()
    logging.info("Bot started: @%s", me.username)

    if ENABLE_API_SYNC:
        await sync_matches(bot)

    await setup_scheduler(bot)

    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить бот"),
        BotCommand(command="rename", description="Изменить имя"),
        BotCommand(command="matches", description="Расписание игр"),
        BotCommand(command="predict", description="Сделать прогноз"),
        BotCommand(command="leaderboard", description="Таблица лидеров"),
        BotCommand(command="form", description="Текущая форма за последние 10 матчей"),
        BotCommand(command="my_stats", description="Моя статистика"),
        BotCommand(command="my_predictions", description="Действующие прогнозы"),
        BotCommand(command="help", description="Правила турнира")
    ])

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        logging.exception("Bot stopped because of an unhandled error")
        raise