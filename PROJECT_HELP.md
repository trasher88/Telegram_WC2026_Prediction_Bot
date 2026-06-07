# Project Help — структура проекта

Карта Telegram-бота турнира прогнозов ЧМ-2026.

Проект разделён на слои:

- `handlers/` — Telegram-команды, callback-кнопки и пользовательские сценарии;
- `repositories/` — SQL-запросы и доступ к SQLite;
- `services/` — бизнес-логика: прогнозы, подсчёт очков, рассылки, статистика;
- `utils/` — форматирование, тексты, флаги, русские названия команд;
- `states/` — FSM-состояния aiogram;
- `middleware/` — глобальная проверка доступа;
- `scheduler.py` — фоновые задачи;
- `web_admin.py` — минимальный read-only web admin через FastAPI.

## Точка входа и конфигурация

| Файл | Назначение |
|---|---|
| `main.py` | Главная точка запуска. Создаёт `Bot`, `Dispatcher`, подключает `AccessMiddleware`, router’ы, инициализирует БД, запускает sync/scheduler/polling и регистрирует команды Telegram. Поддерживает `TELEGRAM_API_BASE_URL` для Cloudflare Worker proxy. |
| `config.py` | Читает переменные окружения: `BOT_TOKEN`, `FOOTBALL_DATA_API_TOKEN`, `ADMIN_IDS`, `APP_TIMEZONE`, `WEB_ADMIN_API_KEY`, `ENABLE_API_SYNC`, `TELEGRAM_API_BASE_URL`. |
| `db.py` | Определяет `DB_PATH`, создаёт SQLite-таблицы через `init_db()`. Текущая схема рассчитана на закрытый invite-only доступ. |
| `api_client.py` | Клиент football-data.org для получения матчей ЧМ-2026. |
| `scheduler.py` | Фоновые задачи: API sync, lock прогнозов, результаты матчей, дневные уведомления. |
| `web_admin.py` | FastAPI-приложение с endpoint’ами `/matches` и `/scores`, закрытое `X-API-Key`. |

## Переменные окружения

| Переменная | Назначение |
|---|---|
| `BOT_TOKEN` | Telegram bot token. Обязательная. |
| `FOOTBALL_DATA_API_TOKEN` | Token football-data.org. Обязательная из-за `config.py`; в тесте можно использовать `disabled`. |
| `ADMIN_IDS` | Telegram ID администраторов через запятую. |
| `APP_TIMEZONE` | Часовой пояс. Для турнира используется `Europe/Moscow`. |
| `WEB_ADMIN_API_KEY` | API key для `web_admin.py`. |
| `DB_PATH` | Путь к SQLite-базе. Если не задан — `wc2026.db` рядом с проектом. |
| `ENABLE_API_SYNC` | Включает/выключает синхронизацию с football-data API. |
| `TELEGRAM_API_BASE_URL` | Опциональный кастомный Telegram API base URL, например Cloudflare Worker. |

## База данных

Основные таблицы создаются в `db.py`.

| Таблица | Назначение |
|---|---|
| `users` | Telegram-пользователи, username/first_name, турнирное имя `display_name`, флаг `name_set`, доступ `is_approved`, timestamps. |
| `invite_codes` | Одноразовые коды приглашений: кто создал, кем использован, время использования, флаг `is_used`. |
| `matches` | Матчи: команды, UTC-время, статус, стадия, тур, счёт, `locked`, `processed`. |
| `predictions` | Прогнозы пользователей. Уникальность: `(user_id, match_id)`. |
| `scores` | Общие очки leaderboard. |
| `processed_matches` | Защита от повторного начисления очков за завершённый матч. |
| `match_notifications` | Защита от повторных lock/result уведомлений по матчу. |
| `daily_notifications` | Защита от повторных дневных уведомлений и итогов игрового дня. |

## Invite-only доступ

Проект работает как закрытый бот.

### Основная логика

1. Администратор вызывает `/invite`.
2. Бот создаёт одноразовый код в `invite_codes`.
3. Бот возвращает ссылку вида `https://t.me/bot_username?start=CODE`.
4. Пользователь открывает ссылку.
5. `/start CODE` проверяет код через `repositories/invites.py`.
6. Если код валидный, пользователь получает `users.is_approved = 1`.
7. Если имя ещё не задано, бот переводит пользователя в FSM ввода имени.
8. Все дальнейшие команды доступны только approved-пользователям.

### Защита

`middleware/access.py` проверяет все входящие сообщения и callback-запросы.

Пропускаются:

- админы из `ADMIN_IDS`;
- `/start`, потому что через него принимается invite-code;
- пользователи с `users.is_approved = 1`.

Все остальные получают отказ.

### Админские команды доступа

| Команда | Назначение |
|---|---|
| `/invite` | Создать одноразовую invite-ссылку. |
| `/approve user_id` | Разрешить пользователя вручную. |
| `/revoke user_id` | Заблокировать пользователя. |

## Scheduler

`scheduler.py` отвечает за фоновые процессы.

| Задача | Условие / время |
|---|---|
| `sync_matches` | Каждые 15 минут, если `ENABLE_API_SYNC=1`. |
| `lock_predictions` | За 5 минут до начала каждого матча. |
| `send_daily_results_summary` | 13:00 МСК — итоги прошедшего игрового дня. |
| `send_daily_matches_digest` | 14:00 МСК — расписание текущего игрового дня. |
| `send_missing_predictions_reminder` | 18:00 МСК — напоминания тем, кто не поставил прогнозы. |
| `send_admin_daily_prediction_report` | 18:30 МСК — админский отчёт. |

Игровой день: `13:00 МСК текущего дня — 12:59 МСК следующего дня`.

## API sync и плей-офф

`sync_matches()` получает матчи из football-data API и обновляет таблицу `matches`.

Перед записью счёта используется `extract_tournament_score(score)`:

- обычный матч — берётся `score.fullTime.home/away`;
- матч с пенальти — к fullTime-счёту добавляется `+1` гол победителю серии;
- `1:1` + победа первой команды по пенальти → `2:1`;
- `1:1` + победа второй команды по пенальти → `1:2`.

## Handlers

| Файл | Назначение |
|---|---|
| `handlers/user.py` | Агрегатор router’ов. Подключает `common`, `matches`, `predictions`, `my_predictions`, `admin`. |
| `handlers/common.py` | `/start` с invite-code, `/rename`, `/help`, ввод и изменение турнирного имени. |
| `handlers/matches.py` | `/matches`, выбор стадии/тура, расписание с флагами и московским временем. |
| `handlers/predictions.py` | `/predict`, выбор матча, выбор счёта, ручной ввод, сохранение прогноза. |
| `handlers/my_predictions.py` | `/my_predictions`, список прогнозов пользователя и начисленные очки. |
| `handlers/leaderboard.py` | `/leaderboard`, таблица лидеров и позиция пользователя. |
| `handlers/player_stats.py` | `/form`, `/my_stats`. |
| `handlers/admin.py` | Админ-команды: invite, approve/revoke, sync, score, rebuild, broadcast, match ids, daily results, stats. |
| `handlers/keyboards.py` | Inline-клавиатуры стадий, туров и быстрых счётов. |

## Middleware

| Файл | Назначение |
|---|---|
| `middleware/access.py` | Глобально блокирует команды и callback-кнопки для пользователей без `is_approved = 1`. |

Middleware подключается в `main.py` до подключения router’ов:

```python
dp.message.middleware(AccessMiddleware())
dp.callback_query.middleware(AccessMiddleware())
```

## Repositories

| Файл | Назначение |
|---|---|
| `repositories/users.py` | Регистрация пользователя, `display_name`, список approved user ID для рассылок. |
| `repositories/invites.py` | Генерация invite-code, использование invite-code, проверка `is_approved`, ручной approve/revoke. |
| `repositories/matches.py` | Матчи по стадиям/турам, доступные матчи для прогноза, score/lock, match ids. |
| `repositories/predictions.py` | Прогнозы пользователя, спрогнозированные match_id, количество прогнозов на матч. |
| `repositories/leaderboard.py` | Данные leaderboard: очки, прогнозы, точные счета, ranking. Учитывает только approved-пользователей. |
| `repositories/player_stats.py` | Данные для `/form` и `/my_stats`. |
| `repositories/admin_stats.py` | Данные для `/users` и `/stats`. |

## Services

| Файл | Назначение |
|---|---|
| `services/predictions.py` | Проверка доступности прогноза, запрет неизвестных команд, lock/deadline/status, атомарное сохранение, расчёт результата прогноза. |
| `services/scoring.py` | Правила очков, обработка завершённого матча, `processed_matches`, полный rebuild очков. |
| `services/match_broadcasts.py` | Lock-рассылка и result-рассылка по конкретному матчу, split длинных сообщений. Рассылки должны идти approved-пользователям. |
| `services/daily_notifications.py` | Расписание игрового дня, напоминания, админский отчёт по прогнозам. Работает с approved-пользователями. |
| `services/daily_results.py` | Итоги прошедшего игрового дня: матчи, дневные очки, точные счета, игрок дня, топ таблицы. |

## States

| Файл | Назначение |
|---|---|
| `states/predict.py` | FSM для сценария прогноза. |
| `states/profile.py` | FSM для ввода/изменения турнирного имени. |

## Utils

| Файл | Назначение |
|---|---|
| `utils/flags.py` | Emoji-флаги команд. |
| `utils/team_names.py` | Русские названия сборных и `team_ru()`. |
| `utils/formatter.py` | Форматирование матчей, UTC → `APP_TIMEZONE`, московское время. |
| `utils/messages.py` | Отправка длинных сообщений частями. |
| `utils/texts.py` | Тексты интерфейса: welcome, help, ошибки, шаблоны. |
| `utils/user_names.py` | Форматирование имени пользователя для сообщений и HTML. |

## Web admin

`web_admin.py` предоставляет:

- `GET /matches`;
- `GET /scores`.

Доступ требует заголовок:

```text
X-API-Key: <WEB_ADMIN_API_KEY>
```

Если `WEB_ADMIN_API_KEY` не задан, endpoint возвращает `503`.

## Cloudflare Worker proxy

Если сервер не может подключиться к `api.telegram.org`, бот может использовать `TELEGRAM_API_BASE_URL`.

В `main.py` используется:

```python
AiohttpSession(api=TelegramAPIServer.from_base(TELEGRAM_API_BASE_URL))
```

Worker URL задаётся в `.env`:

```env
TELEGRAM_API_BASE_URL=https://telegram-bot-api-proxi.example.workers.dev
```

## Навигация по потоку данных

### Invite-регистрация

1. Админ вызывает `/invite`.
2. `handlers/admin.py` вызывает `create_invite_code()`.
3. Код сохраняется в `invite_codes`.
4. Пользователь открывает `/start CODE`.
5. `handlers/common.py` вызывает `use_invite_code()`.
6. Пользователь получает `is_approved = 1`.
7. Далее запускается обычный сценарий ввода имени.

### Прогноз

1. `/predict` приходит в `handlers/predictions.py`.
2. `AccessMiddleware` проверяет доступ пользователя.
3. Handler выбирает матч через `repositories/matches.py`.
4. Доступность проверяется в `services/predictions.py`.
5. Прогноз сохраняется в `predictions`.
6. Пользователь получает подтверждение.

### Завершение матча

1. `scheduler.py` получает `finished` из API или админ вызывает `/set_score`.
2. Счёт записывается в `matches`.
3. `services/scoring.py` начисляет очки.
4. `services/match_broadcasts.py` отправляет результат прогнозов.
5. `/leaderboard`, `/form`, `/my_stats` отражают обновлённые данные.

### Итоги игрового дня

1. В 13:00 `scheduler.py` вызывает `send_daily_results_summary()`.
2. `services/daily_results.py` берёт предыдущий игровой день.
3. Собирает завершённые матчи и прогнозы.
4. Считает дневные очки через `calculate_points()`.
5. Формирует сообщение и отправляет approved-пользователям.
6. Фиксирует отправку в `daily_notifications`.

## Работа с новой базой

Если используется `db.py` без миграций, старая SQLite-база со старой структурой не обновится автоматически.

Для нового турнира рекомендуется создать чистую базу:

```bash
systemctl stop wc2026-bot

cp wc2026.db wc2026_backup_$(date +%Y%m%d_%H%M).db
mv wc2026.db wc2026_old.db

set -a
source .env
set +a

python main.py
```

После первого запуска проверить:

```bash
sqlite3 wc2026.db
```

```sql
.tables
PRAGMA table_info(users);
SELECT id, is_approved FROM users;
.quit
```

В `users` должна быть колонка `is_approved`, а админы из `ADMIN_IDS` должны иметь `is_approved = 1`.

## Важные правила проекта

- В `handlers/` не размещать прямой SQL без необходимости.
- SQL держать в `repositories/`.
- Бизнес-логику держать в `services/`.
- Общие тексты — в `utils/texts.py`.
- Форматирование команд/флагов/времени — в `utils/`.
- Глобальную проверку доступа держать в `middleware/`.
- Не коммитить `.env`, SQLite-базы, `.idea`, `.venv`, `__pycache__`.
- Для тестовой базы использовать `ENABLE_API_SYNC=0`.
- Для ручного результата использовать `/set_score`, а не прямое изменение `processed` в БД.
