from html import escape


# COMMON
ACCESS_DENIED = "⛔ Доступ запрещён"
INVALID_FORMAT = (
    "❌ Неверный формат\n"
    "Используй формат: 2:1"
)

NEED_TEXT_SCORE = (
    "❌ Отправь счёт текстом.\n"
    "Например: 2:1"
)

UNREAL_SCORE = (
    "❌ Счёт выглядит слишком большим.\n"
    "Введи реальный футбольный счёт, например: 2:1"
)

GAME_NOT_CHOOSE = "❌ Матч не выбран. Начни заново через /predict"

NO_MATCHES_FOUND = "Матчи не найдены"
NO_MATCHES_AVAILABLE = "Нет доступных матчей"
MATCH_NOT_FOUND = "❌ Матч не найден"
NO_PREDICTIONS_YET = "У тебя пока нет прогнозов"


# START
WELCOME = (
    "Добро пожаловать в бот прогнозов ⚽️ЧМ-2026!\n\n"
    "/matches — расписание матчей\n"
    "/predict — сделать прогноз\n"
    "/leaderboard — таблица лидеров\n"
    "/form — текущая форма за последние 10 матчей\n"
    "/my_stats — моя статистика\n"
    "/my_predictions — мои прогнозы\n"
    "/rename — изменить имя\n"
    "/help — правила турнира"
)



ASK_DISPLAY_NAME = (
    "Привет! Как тебя подписать в таблице турнира?\n"
    "Отправь имя одним сообщением. Например: Иван"
)

ASK_RENAME_DISPLAY_NAME = (
    "Введи новое имя для таблицы турнира (от 2 до 30 символов)"
)

DISPLAY_NAME_NEED_TEXT = "Отправь имя текстом, пожалуйста."


def display_name_invalid(reason: str) -> str:
    return f"❌ Не могу сохранить имя: {reason}. Попробуй ещё раз."


def display_name_saved(display_name: str) -> str:
    return f"✅ Имя сохранено: {display_name}"


def display_name_renamed(display_name: str) -> str:
    return f"✅ Имя обновлено: {display_name}"


# MENUS
CHOOSE_STAGE = "📅 Выбери стадию турнира:"
CHOOSE_PREDICTION_STAGE = "🎯 Выбери стадию для прогноза:"
CHOOSE_MATCH = "Выбери матч:"
SEND_PREDICTION = (
    "Отправь прогноз в формате: 2:1"
)


# BUTTONS
ROUND_1 = "Тур 1️⃣"
ROUND_2 = "Тур 2️⃣"
ROUND_3 = "Тур 3️⃣"
LAST_32 = "1/16 ⚔️ финала"
LAST_16 = "1/8 ⚔️ финала"
QUARTER_FINALS = "1/4 ⚔️ финала"
SEMI_FINALS = "⚔️ Полуфинал"
THIRD_PLACE = "🥉 Матч за 3-е место"
FINAL = "🏆 Финал"


# PREDICTIONS
def prediction_saved(home_team: str, away_team: str, home_pred: int, away_pred: int) -> str:
    return (
        "✅ Прогноз сохранён\n\n"
        f"{escape(home_team)}\n"
        f"{home_pred}:{away_pred}\n"
        f"{escape(away_team)}"
    )


def predictions_closed(home_team: str, away_team: str) -> str:
    return (
        "⛔ Приём прогнозов закрыт\n\n"
        f"{escape(home_team)} vs {escape(away_team)}"
    )


MATCH_ALREADY_STARTED = "⛔ Матч уже начался"
MATCH_ALREADY_STARTED_OR_END = "⛔ Матч уже начался или завершён"



# MY PREDICTIONS
MY_PREDICTIONS_TITLE = "📋 <b>Мои прогнозы</b>\n\n"

RESULT_SCHEDULED = "⏳ Ожидает результата"
RESULT_EXACT = "✅ Точный счёт (2)"
RESULT_OUTCOME = "🟡 Угадан исход (1)"
RESULT_LOST = "❌ Не угадано"

PREDICTION_LABEL = "🎯 Прогноз"



# MATCHES
MATCHES_TITLE = "⚽ Матчи:\n\n"

def group_stage_round(round_number: int) -> str:
    return f"🌍 Групповой этап — тур {round_number}\n\n"


CHOOSE_SCORE = "🎯 Выбери прогноз или введи свой вариант\n\n"
ANOTHER_SCORE = "Другой счёт\n\n"



# LEADERBOARD
LEADERBOARD_TITLE = "🏆 <b>ТАБЛИЦА ЛИДЕРОВ ТУРНИРА ПРОГНОЗОВ ЧМ-2026</b>\n\n"
YOUR_POSITION = "<b>Текущая позиция</b>"


def points_word(points: int) -> str:
    points = abs(points)

    if points % 10 == 1 and points % 100 != 11:
        return "очко"

    if points % 10 in [2, 3, 4] and points % 100 not in [12, 13, 14]:
        return "очка"

    return "очков"


def format_points(points: int) -> str:
    return f"{points} {points_word(points)}"


# ADMIN
REBUILD_STARTED = "♻️ Пересчитываю очки..."
REBUILD_SUCCESS = "✅ Очки успешно пересчитаны"
FORCE_SYNC_STARTED = "🔄 Синхронизация матчей запущена..."
FORCE_SYNC_SUCCESS = "✅ Синхронизация завершена"

SET_SCORE_USAGE = (
    "Использование:\n"
    "/set_score match_id home_score away_score"
)

MATCH_INFO_USAGE = "Использование: /match_info match_id"

BROADCAST_USAGE = "Использование: /broadcast сообщение"


def rebuild_error(error: Exception) -> str:
    return f"❌ Ошибка пересчёта:\n{error}"



def sync_error(error: Exception) -> str:
    return f"❌ Ошибка синхронизации:\n{error}"


def score_updated(match_id: int, home: int, away: int) -> str:
    return (
        "✅ Счёт обновлён\n"
        f"Матч {match_id}: {home}:{away}"
    )


def score_processing_error(error: Exception) -> str:
    return f"❌ Ошибка обработки матча:\n{error}"


def broadcast_done(sent: int, failed: int) -> str:
    return (
        "📣 Рассылка завершена\n\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )


# REMINDERS
REMINDER_ONE_HOUR = "⚽ Матч начнётся через 1 час!"
REMINDER_TEN_MINUTES = "⚽ Осталось 10 минут, чтобы сделать прогноз!"


# HELP
HELP_TEXT = (
    "ℹ️ Правила турнира прогнозов ЧМ-2026\n\n"

    "🎯 Начисление очков\n"
    "• Точный счёт — 2 очка\n"
    "• Угадан исход матча — 1 очко\n"
    "• Прогноз не сыграл — 0 очков\n\n"

    "Пример:\n"
    "Матч закончился 2:1.\n"
    "Прогноз 2:1 — 2 очка.\n"
    "Прогноз 1:0 или 3:2 — 1 очко.\n"
    "Прогноз 1:1 или 0:2 — 0 очков.\n\n"
    
    "Матч закончился 2:2.\n"
    "Прогноз 2:2 — 2 очка.\n"
    "Прогноз 1:1 или 3:3 — 1 очко.\n\n"
    
    "🏁 Плей-офф и серия пенальти\n"
    "Если матч на вылет дошёл до серии пенальти, победителю серии добавляется +1 гол.\n"
    "Например, если матч закончился 1:1, а первая команда выиграла по пенальти, "
    "для прогнозов считается счёт 2:1.\n"
    "Если по пенальти выиграла вторая команда, считается счёт 1:2.\n"
    "Для расчёта прогнозов такой матч считается победой одной из команд, а не ничьей.\n\n"

    "🔒 Когда закрываются прогнозы\n"
    "Время матчей в боте указано по Москве.\n"
    "Прогноз можно поставить или изменить до закрытия приёма прогнозов.\n"
    "Приём закрывается за 5 минут до начала матча.\n"
    "После закрытия изменить прогноз уже нельзя.\n\n"

    "📅 Игровой день\n"
    "Игровой день считается по Москве:\n"
    "с 13:00 текущего дня до 12:59 следующего дня.\n"
    "В один игровой день попадают вечерние и ночные матчи по московскому времени.\n\n"

    "🔔 Уведомления\n"
    "• 13:00 — итоги прошедшего игрового дня\n"
    "• 14:00 — расписание текущего игрового дня\n"
    "• 18:00 — напоминание тем, кто не поставил прогнозы\n\n"

    "🏆 Таблица лидеров\n"
    "В таблице показываются очки, количество точных счетов и количество прогнозов.\n"
    "Если у игроков одинаковое количество очков, выше будет тот, у кого больше точных счетов.\n\n"

    "📈 Форма игрока\n"
    "/form показывает последние 10 завершённых прогнозов игрока:\n"
    "точные счета, угаданные исходы, промахи, очки за форму и средний балл.\n\n"

    "👤 Статистика игрока\n"
    "/my_stats показывает общую карточку игрока:\n"
    "очки, точные счета, угаданные исходы, промахи, завершённые прогнозы, ожидающие прогнозы, "
    "точность и текущую серию.\n\n"

    "📊 Пояснение статистики\n"
    "• Очковая эффективность — сколько очков набрано от максимально возможного количества.\n"
    "  Формула: очки / максимум очков × 100%\n\n"
    "• Прогнозная точность — процент прогнозов, где игрок получил хотя бы 1 очко.\n"
    "  Формула: (точные счета + угаданные исходы) / завершённые прогнозы × 100%\n\n"
    "• Точность счетов — это процент прогнозов, где игрок угадал точный счёт.\n"
    "  Формула: точные счета / завершённые прогнозы × 100%\n\n"
    "• Средний балл — среднее количество очков за завершённые прогнозы.\n"
    "  Формула: очки / завершённые прогнозы\n\n"

    "📌 Полезные команды\n"
    "/matches — расписание матчей\n"
    "/predict — сделать прогноз\n"
    "/leaderboard — таблица лидеров\n"
    "/form — моя форма за последние 10 матчей\n"
    "/my_stats — моя статистика\n"
    "/my_predictions — мои прогнозы\n"
    "/rename — изменить имя\n"
    "/help — правила турнира"
)