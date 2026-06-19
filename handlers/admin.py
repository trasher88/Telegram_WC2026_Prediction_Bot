from aiogram import Bot, F, Router, types
from aiogram.filters import Command

from config import ADMIN_IDS
from repositories.admin_stats import (
    get_tournament_stats,
    get_users_dashboard_data,
    is_match_processed,
)
from repositories.matches import (
    get_match_info,
    list_match_ids,
    list_match_ids_by_group_round,
    list_match_ids_by_stage,
    lock_match,
    set_match_score_finished
)
from repositories.predictions import count_predictions_for_match
from repositories.users import list_user_ids
from repositories.invites import approve_user, create_invite_code, revoke_user
from scheduler import sync_matches
from services.match_broadcasts import (
    reset_notification,
    send_lock_predictions_broadcast,
    send_result_predictions_broadcast,
)
from services.scoring import rebuild_all_scores
from utils import texts as T
from utils.team_names import team_ru
from utils.user_names import user_display_name
from handlers.keyboards import STAGE_TITLES, tournament_stage_keyboard

from utils.formatter import format_moscow_datetime

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import APP_TIMEZONE
from services.daily_results import (
    build_daily_results_summary,
    previous_game_day,
    reset_daily_results_notification,
    send_daily_results_summary,
)

from services.round_stats import (
    build_group_round_stats_summary,
    build_stage_stats_summary,
    send_group_round_stats_summary,
    send_stage_stats_summary,
)

from config import ENABLE_API_SYNC

router = Router()


def is_admin(user_id: int) -> bool:
    return int(user_id) in ADMIN_IDS


@router.message(Command("admin"))
async def admin_menu(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    text = (
        "🛠 <b>Админ-панель</b>\n\n"

        "⚙️ <b>Синхронизация и очки</b>\n"
        "/force_sync — синхронизировать матчи с API\n"
        "/rebuild_scores — пересчитать все очки\n\n"

        "⚽ <b>Матчи</b>\n"
        "/match_ids — показать ID ближайших матчей\n"
        "/match_info match_id — информация о матче\n"
        "/set_score match_id home away — вручную установить счёт\n\n"

        "🔒 <b>Прогнозы и lock</b>\n"
        "/test_lock match_id — закрыть прогнозы и отправить lock-рассылку\n\n"

        "📣 <b>Рассылки</b>\n"
        "/broadcast текст — отправить сообщение всем пользователям\n"
        "/round_stats matchday — предпросмотр статистики группового тура\n"
        "/round_stats_send matchday — отправить статистику группового тура всем\n"
        "/stage_stats stage — предпросмотр статистики стадии плей-офф\n"
        "/stage_stats_send stage — отправить статистику стадии плей-офф всем\n"
        "/daily_results — предпросмотр итогов прошлого игрового дня\n"
        "/daily_results_send — отправить итоги прошлого игрового дня всем\n\n"

        "👥 <b>Пользователи и статистика</b>\n"
        "/users — список и активность пользователей\n"
        "/invite — создать одноразовую ссылку-приглашение\n"
        "/approve user_id — разрешить пользователя\n"
        "/revoke user_id — заблокировать пользователя\n"
        "/stats — статистика турнира и системы\n\n"

        "📌 <b>Примеры</b>\n"
        "<code>/set_score 537357 2 2</code>\n"
        "<code>/match_info 537357</code>\n"
        "<code>/test_lock 537357</code>\n"
        "<code>/broadcast Всем привет!</code>\n"
        "<code>Рассылка статистики<code>\n"
        "<code>/round_stats 1<code>\n"
        "<code>/round_stats 2<code>\n"
        "<code>/round_stats 3<code>\n"
        "<code>/stage_stats 1_16<code>\n"
        "<code>/stage_stats 1_8<code>\n"
        "<code>/stage_stats 1_4<code>\n"
        "<code>/stage_stats 1_2<code>\n"
        "<code>/stage_stats third<code>\n"
        "<code>/stage_stats final<code>\n"
    )

    await msg.answer(text, parse_mode="HTML")


def _format_match_ids_list(matches) -> str:
    text = ""

    for (
        match_id,
        home_team,
        away_team,
        start_time,
        status,
        stage,
        matchday
    ) in matches:
        text += (
            f"🆔 <code>{match_id}</code>\n"
            f"⚽ {team_ru(home_team)} — {team_ru(away_team)}\n"
            f"📅 {format_moscow_datetime(start_time)} МСК\n"
            f"📌 {status}\n\n"
        )

    return text


async def _send_long_admin_text(message: types.Message, text: str):
    max_len = 3900

    if len(text) <= max_len:
        await message.answer(text, parse_mode="HTML")
        return

    chunks = []
    current = ""

    for block in text.split("\n\n"):
        block = block.strip()

        if not block:
            continue

        candidate = f"{current}\n\n{block}" if current else block

        if len(candidate) > max_len:
            chunks.append(current)
            current = block
        else:
            current = candidate

    if current:
        chunks.append(current)

    for chunk in chunks:
        await message.answer(chunk, parse_mode="HTML")


@router.message(Command("rebuild_scores"))
async def rebuild_scores_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    await msg.answer(T.REBUILD_STARTED)

    try:
        await rebuild_all_scores()
        await msg.answer(T.REBUILD_SUCCESS)
    except Exception as e:
        await msg.answer(T.rebuild_error(e))


@router.message(Command("force_sync"))
async def force_sync_cmd(msg: types.Message, bot: Bot):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    if not ENABLE_API_SYNC:
        await msg.answer(
            "⚠️ API-синхронизация отключена через ENABLE_API_SYNC=0.\n"
            "Команда /force_sync не выполнена, чтобы не перезаписать тестовую базу."
        )
        return

    await msg.answer(T.FORCE_SYNC_STARTED)

    try:
        await sync_matches(bot)
        await msg.answer(T.FORCE_SYNC_SUCCESS)
    except Exception as e:
        await msg.answer(T.sync_error(e))


@router.message(Command("set_score"))
async def set_score_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    parts = msg.text.split()

    if len(parts) != 4:
        await msg.answer(T.SET_SCORE_USAGE)
        return

    try:
        _, match_id_raw, home_raw, away_raw = parts
        match_id = int(match_id_raw)
        home = int(home_raw)
        away = int(away_raw)
    except ValueError:
        await msg.answer(T.SET_SCORE_USAGE)
        return

    await set_match_score_finished(match_id, home, away)

    try:
        await rebuild_all_scores()

        await reset_notification(
            match_id=match_id,
            notification_type="result"
        )

        await send_result_predictions_broadcast(
            bot=msg.bot,
            match_id=match_id
        )

        await msg.answer(
            f"{T.REBUILD_SUCCESS}\n"
            f"Матч {match_id}: {home}:{away}"
        )
    except Exception as e:
        await msg.answer(T.score_processing_error(e))


@router.message(Command("match_info"))
async def match_info(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    parts = msg.text.split()

    if len(parts) != 2:
        await msg.answer(T.MATCH_INFO_USAGE)
        return

    try:
        match_id = int(parts[1])
    except ValueError:
        await msg.answer(T.MATCH_INFO_USAGE)
        return

    match = await get_match_info(match_id)

    if not match:
        await msg.answer(T.MATCH_NOT_FOUND)
        return

    preds_count = await count_predictions_for_match(match_id)
    processed = await is_match_processed(match_id)

    text = (
        f"📊 Информация о матче\n\n"
        f"ID: {match_id}\n"
        f"{team_ru(match[0])} — {team_ru(match[1])}\n\n"
        f"Статус: {match[2]}\n"
        f"Счёт: {match[3]}:{match[4]}\n"
        f"Начало: {match[5]}\n\n"
        f"Прогнозов: {preds_count}\n"
        f"Обработан: {'да' if processed else 'нет'}"
    )

    await msg.answer(text)


@router.message(Command("broadcast"))
async def broadcast(msg: types.Message, bot: Bot):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    text = msg.text.replace("/broadcast", "").strip()

    if not text:
        await msg.answer(T.BROADCAST_USAGE)
        return

    user_ids = await list_user_ids()

    sent = 0
    failed = 0

    for user_id in user_ids:
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except Exception:
            failed += 1

    await msg.answer(T.broadcast_done(sent, failed))


@router.message(Command("users"))
async def users_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    dashboard = await get_users_dashboard_data()
    top = dashboard["top_activity"]

    text = (
        "👥 <b>Пользователи</b>\n\n"
        f"Всего пользователей: <b>{dashboard['total_users']}</b>\n"
        f"Активных прогнозистов: <b>{dashboard['active_predictors']}</b>\n\n"
        "🏆 Топ по активности:\n\n"
    )

    for i, row in enumerate(top, start=1):
        user_id = row[0]
        display_name = row[1]
        username = row[2]
        first_name = row[3]
        preds = row[4]

        name = user_display_name(
            user_id,
            display_name=display_name,
            username=username,
            first_name=first_name,
            html=True,
            include_username=True,
        )
        text += f"{i}. {name} — прогнозов: {preds}\n"

    await msg.answer(text, parse_mode="HTML")


@router.message(Command("stats"))
async def stats_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    stats = await get_tournament_stats()

    text = (
        "📊 Статистика турнира\n\n"

        "⚽ Матчи:\n"
        f"• Всего: {stats['total_matches']}\n"
        f"• Завершено: {stats['finished_matches']}\n"
        f"• В прямом эфире: {stats['live_matches']}\n\n"

        "🎯 Прогнозы:\n"
        f"• Всего: {stats['total_predictions']}\n\n"

        "👥 Пользователи:\n"
        f"• Всего: {stats['total_users']}\n"
        f"• Активных: {stats['active_users']}\n\n"

        "🧠 Система:\n"
        f"• Обработано матчей: {stats['processed_matches']}\n"
    )

    await msg.answer(text)


@router.message(Command("match_ids"))
async def match_ids_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    await msg.answer(
        "🆔 Выбери этап, для которого показать ID матчей:",
        reply_markup=tournament_stage_keyboard(
            group_prefix="admin_match_ids_group_",
            stage_prefix="admin_match_ids_stage_"
        )
    )


@router.callback_query(F.data.startswith("admin_match_ids_group_"))
async def admin_match_ids_group(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(T.ACCESS_DENIED, show_alert=True)
        return

    round_number = int(callback.data.replace("admin_match_ids_group_", ""))

    matches = await list_match_ids_by_group_round(round_number)

    if not matches:
        await callback.message.answer(T.NO_MATCHES_FOUND)
        await callback.answer()
        return

    text = (
        f"🆔 <b>ID матчей</b>\n"
        f"🌍 Групповой турнир: Тур {round_number}\n\n"
    )

    text += _format_match_ids_list(matches)

    await _send_long_admin_text(callback.message, text)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_match_ids_stage_"))
async def admin_match_ids_stage(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(T.ACCESS_DENIED, show_alert=True)
        return

    stage = callback.data.replace("admin_match_ids_stage_", "")

    matches = await list_match_ids_by_stage(stage)

    if not matches:
        await callback.message.answer(T.NO_MATCHES_FOUND)
        await callback.answer()
        return

    stage_title = STAGE_TITLES.get(stage, stage)

    text = (
        f"🆔 <b>ID матчей</b>\n"
        f"🏷 {stage_title}\n\n"
    )

    text += _format_match_ids_list(matches)

    await _send_long_admin_text(callback.message, text)
    await callback.answer()


@router.message(Command("test_lock"))
async def test_lock_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    parts = msg.text.split()

    if len(parts) != 2:
        await msg.answer("Использование: /test_lock match_id")
        return

    try:
        match_id = int(parts[1])
    except ValueError:
        await msg.answer("match_id должен быть числом")
        return

    await reset_notification(
        match_id=match_id,
        notification_type="lock"
    )

    await lock_match(match_id)

    await send_lock_predictions_broadcast(
        bot=msg.bot,
        match_id=match_id
    )

    await msg.answer("✅ Матч закрыт, lock-рассылка отправлена")


@router.message(Command("daily_results"))
async def daily_results_preview_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    game_day = previous_game_day()

    text, error = await build_daily_results_summary(game_day)

    if error:
        await msg.answer(f"⚠️ {error}")
        return

    if not text:
        await msg.answer("⚠️ Итоги игрового дня пустые")
        return

    await _send_long_admin_text(msg, text)


@router.message(Command("daily_results_send"))
async def daily_results_send_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    game_day = previous_game_day()

    await reset_daily_results_notification(game_day)

    await msg.answer(
        "📊 Отправляю итоги прошлого игрового дня всем пользователям..."
    )

    await send_daily_results_summary(
        bot=msg.bot,
        game_day=game_day,
        force=True,
    )

    await msg.answer("✅ Итоги игрового дня отправлены")


@router.message(Command("invite"))
async def invite_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    code = await create_invite_code(msg.from_user.id)

    bot_info = await msg.bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start={code}"

    await msg.answer(
        "🔗 <b>Ссылка-приглашение создана</b>\n\n"
        f"<code>{invite_link}</code>\n\n"
        "Ссылка одноразовая. После первого входа код будет использован.",
        parse_mode="HTML",
    )


@router.message(Command("approve"))
async def approve_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    parts = msg.text.split()

    if len(parts) != 2 or not parts[1].isdigit():
        await msg.answer("Использование: /approve user_id")
        return

    user_id = int(parts[1])

    await approve_user(user_id)

    await msg.answer(f"✅ Пользователь {user_id} получил доступ")


@router.message(Command("revoke"))
async def revoke_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    parts = msg.text.split()

    if len(parts) != 2 or not parts[1].isdigit():
        await msg.answer("Использование: /revoke user_id")
        return

    user_id = int(parts[1])

    await revoke_user(user_id)

    await msg.answer(f"⛔ Доступ пользователя {user_id} отключён")


@router.message(Command("round_stats"))
async def round_stats_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    parts = msg.text.split()

    if len(parts) != 2 or not parts[1].isdigit():
        await msg.answer(
            "Использование: /round_stats matchday\n"
            "Например: /round_stats 1"
        )
        return

    matchday = int(parts[1])

    text, error = await build_group_round_stats_summary(
        matchday=matchday,
    )

    if error:
        await msg.answer(f"⚠️ {error}")
        return

    if not text:
        await msg.answer("⚠️ Отчёт пустой")
        return

    await _send_long_admin_text(msg, text)


@router.message(Command("round_stats_send"))
async def round_stats_send_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    parts = msg.text.split()

    if len(parts) != 2 or not parts[1].isdigit():
        await msg.answer(
            "Использование: /round_stats_send matchday\n"
            "Например: /round_stats_send 1"
        )
        return

    matchday = int(parts[1])

    await msg.answer(
        f"📊 Отправляю статистику {matchday}-го группового тура всем пользователям..."
    )

    ok, error = await send_group_round_stats_summary(
        bot=msg.bot,
        matchday=matchday,
    )

    if not ok:
        await msg.answer(f"⚠️ {error}")
        return

    await msg.answer("✅ Статистика группового тура отправлена")


@router.message(Command("stage_stats"))
async def stage_stats_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    parts = msg.text.split()

    if len(parts) != 2:
        await msg.answer(
            "Использование: /stage_stats stage\n\n"
            "Примеры:\n"
            "/stage_stats 1_16\n"
            "/stage_stats 1_8\n"
            "/stage_stats 1_4\n"
            "/stage_stats 1_2\n"
            "/stage_stats third\n"
            "/stage_stats final"
        )
        return

    raw_stage = parts[1]

    text, error = await build_stage_stats_summary(
        raw_stage=raw_stage,
    )

    if error:
        await msg.answer(f"⚠️ {error}")
        return

    if not text:
        await msg.answer("⚠️ Отчёт пустой")
        return

    await _send_long_admin_text(msg, text)


@router.message(Command("stage_stats_send"))
async def stage_stats_send_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer(T.ACCESS_DENIED)
        return

    parts = msg.text.split()

    if len(parts) != 2:
        await msg.answer(
            "Использование: /stage_stats_send stage\n\n"
            "Примеры:\n"
            "/stage_stats_send 1_16\n"
            "/stage_stats_send 1_8\n"
            "/stage_stats_send 1_4\n"
            "/stage_stats_send 1_2\n"
            "/stage_stats_send third\n"
            "/stage_stats_send final"
        )
        return

    raw_stage = parts[1]

    await msg.answer(
        f"📊 Отправляю статистику этапа {raw_stage} всем пользователям..."
    )

    ok, error = await send_stage_stats_summary(
        bot=msg.bot,
        raw_stage=raw_stage,
    )

    if not ok:
        await msg.answer(f"⚠️ {error}")
        return

    await msg.answer("✅ Статистика этапа отправлена")