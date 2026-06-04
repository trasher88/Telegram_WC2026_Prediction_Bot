# Run Checklist — запуск, проверка и деплой

Практический чек-лист для локального теста, серверного запуска и боевого режима Telegram-бота прогнозов ЧМ-2026.

## 0. Проверка перед GitHub

Перед первым `git push` убедиться, что в репозиторий не попадут:

```text
.env
*.db
.idea/
.venv/
__pycache__/
*.pyc
```

Проверить:

```bash
git status
git ls-files
```

Если файл уже попал в индекс:

```bash
git rm --cached .env
git rm --cached wc2026.db
git rm --cached test_wc2026.db
```

## 1. Локальное окружение

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 2. Переменные окружения

Проект читает настройки через `os.getenv()`.

Если запускаешь вручную на Linux:

```bash
set -a
source .env
set +a
```

Пример тестового `.env`:

```env
BOT_TOKEN=123456789:telegram_bot_token
FOOTBALL_DATA_API_TOKEN=disabled
ADMIN_IDS=123456789
APP_TIMEZONE=Europe/Moscow
WEB_ADMIN_API_KEY=test-local-key

DB_PATH=/root/wc2026/test/Telegram_WC2026_Prediction_Bot/test_wc2026.db
ENABLE_API_SYNC=0

TELEGRAM_API_BASE_URL=https://telegram-bot-api-proxi.6trasher6.workers.dev
```

Не писать inline-комментарии после значений:

```env
# плохо
ENABLE_API_SYNC=0 # test

# хорошо
# test mode
ENABLE_API_SYNC=0
```

## 3. Режимы запуска

### Тестовый режим

```env
DB_PATH=.../test_wc2026.db
ENABLE_API_SYNC=0
FOOTBALL_DATA_API_TOKEN=disabled
```

Назначение:

- не ходить в football-data API;
- тестировать локальные/ручные матчи;
- безопасно проверять `/set_score`, `/rebuild_scores`, `/leaderboard`, `/form`, `/my_stats`, `/daily_results`.

### Боевой режим

```env
DB_PATH=.../wc2026.db
ENABLE_API_SYNC=1
FOOTBALL_DATA_API_TOKEN=real_token
```

Назначение:

- синхронизировать матчи и результаты через football-data API;
- обрабатывать завершённые матчи автоматически;
- вести настоящий турнир.

## 4. Cloudflare Worker proxy для Telegram

Если сервер не может подключиться к `api.telegram.org`, проверить Worker:

```bash
set -a
source .env
set +a

curl -sS --connect-timeout 10 --max-time 30 \
"$TELEGRAM_API_BASE_URL/bot$BOT_TOKEN/getMe"
```

Ожидаемо:

```json
{"ok":true,"result":{...}}
```

Если корневой URL Worker открывается как `Not found`, это нормально. Если открывается `Hello World`, значит в Worker ещё стоит шаблонный код, а не proxy-код.

## 5. Проверка синтаксиса

Не запускать `compileall` по всей папке проекта, если внутри есть `.venv`:

```bash
# не рекомендуется на маленьком VPS
python -m compileall -q .
```

Правильно:

```bash
python -m compileall -q main.py config.py db.py scheduler.py api_client.py handlers repositories services states utils
```

## 6. Проверка football-data API

В тестовом режиме этот шаг можно пропустить.

В боевом режиме:

```bash
python tests/test_api.py
```

Ожидаемо:

- HTTP status `200`;
- ответ содержит данные API.

Если `401`, проблема в `FOOTBALL_DATA_API_TOKEN`.

## 7. Ручной запуск

```bash
cd /root/wc2026/test/Telegram_WC2026_Prediction_Bot
source .venv/bin/activate
set -a
source .env
set +a

python main.py
```

Ожидаемо:

```text
Bot started: @...
SCHEDULER READY
```

Остановить ручной запуск:

```text
Ctrl+C
```

## 8. Smoke-test пользовательских команд

Проверить в Telegram:

| Команда | Что проверить |
|---|---|
| `/start` | При первом запуске бот просит имя, сохраняет `display_name`. |
| `/rename` | Имя меняется в лидерборде и статистике. |
| `/help` | Правила турнира, очки, игровой день, уведомления, пенальти. |
| `/matches` | Кнопки стадий, московское время, флаги, русские названия. |
| `/predict` | Выбор стадии, матча, счёта; прогноз сохраняется. |
| `/my_predictions` | Прогнозы пользователя, статусы и очки. |
| `/leaderboard` | Очки, точные счета, количество прогнозов, правильный порядок. |
| `/form` | Последние 10 завершённых прогнозов. |
| `/my_stats` | Карточка игрока и проценты. |

Отдельно проверить: матчи с неизвестными командами не должны появляться в `/predict`, но могут отображаться в `/matches`.

## 9. Smoke-test админских команд

Проверить админом из `ADMIN_IDS`:

| Команда | Что проверить |
|---|---|
| `/admin` | Список команд. |
| `/match_ids` | Сначала кнопки стадий/туров, потом ID матчей. Время по Москве. |
| `/match_info <match_id>` | Команды, статус, счёт, время, количество прогнозов, processed. |
| `/set_score <match_id> <home> <away>` | Матч становится `finished`, `locked=1`, очки пересчитываются, результат рассылается. |
| `/rebuild_scores` | Полный пересчёт очков. |
| `/force_sync` | При `ENABLE_API_SYNC=0` не выполняется; при `1` запускает API sync. |
| `/daily_results` | Предпросмотр итогов прошлого игрового дня. |
| `/daily_results_send` | Ручная отправка итогов всем пользователям. |
| `/users` | Активность пользователей. |
| `/stats` | Турнирная и системная статистика. |
| `/broadcast <text>` | Массовая рассылка. |
| `/test_lock <match_id>` | Закрытие прогнозов и lock-рассылка. |

## 10. Проверка дневных уведомлений

Актуальное расписание:

| Время МСК | Уведомление |
|---|---|
| 13:00 | Итоги прошедшего игрового дня всем пользователям. |
| 14:00 | Расписание текущего игрового дня всем пользователям. |
| 18:00 | Напоминание тем, кто не поставил все прогнозы. |
| 18:30 | Админский отчёт. |

Для теста можно временно поменять время cron-задач в `scheduler.py`, но перед боем вернуть:

```python
hour=13, minute=0
hour=14, minute=0
hour=18, minute=0
hour=18, minute=30
```

## 11. Проверка итогов игрового дня

Для тестовой базы:

1. Убедиться, что в базе есть матчи прошедшего игрового дня.
2. Поставить прогнозы несколькими пользователями.
3. Закрыть матчи через `/set_score`.
4. Выполнить `/daily_results`.
5. Проверить формат сообщения.
6. Выполнить `/daily_results_send`, если нужно отправить всем.

Итоги не отправляются автоматически, если:

- матчей за прошлый игровой день нет;
- не все матчи прошедшего игрового дня `finished`;
- у какого-то завершённого матча нет счёта.

## 12. Проверка правила пенальти

Ожидаемая логика:

```text
fullTime 1:1, penalties 4:3 -> 2:1
fullTime 1:1, penalties 2:4 -> 1:2
fullTime 2:1, penalties отсутствует -> 2:1
```

Если результат выставляется вручную через `/set_score`, админ вводит уже итоговый турнирный счёт.

## 13. Запуск через systemd

Создать unit:

```bash
nano /etc/systemd/system/wc2026-bot.service
```

Пример:

```ini
[Unit]
Description=Telegram WC2026 Prediction Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/wc2026/test/Telegram_WC2026_Prediction_Bot
EnvironmentFile=/root/wc2026/test/Telegram_WC2026_Prediction_Bot/.env
ExecStart=/root/wc2026/test/Telegram_WC2026_Prediction_Bot/.venv/bin/python /root/wc2026/test/Telegram_WC2026_Prediction_Bot/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запуск:

```bash
systemctl daemon-reload
systemctl enable wc2026-bot
systemctl start wc2026-bot
systemctl status wc2026-bot
journalctl -u wc2026-bot -f
```

Остановить:

```bash
systemctl stop wc2026-bot
```

Перезапустить:

```bash
systemctl restart wc2026-bot
```

## 14. Обновление кода с GitHub

Локально:

```bash
git add .
git commit -m "Update bot"
git push
```

На сервере:

```bash
cd /root/wc2026/test/Telegram_WC2026_Prediction_Bot
systemctl stop wc2026-bot

git pull

source .venv/bin/activate
pip install -r requirements.txt
python -m compileall -q main.py config.py db.py scheduler.py api_client.py handlers repositories services states utils

systemctl start wc2026-bot
journalctl -u wc2026-bot -f
```

## 15. Диагностика частых проблем

### `Killed`

Проверить:

```bash
dmesg -T | tail -50
```

Если есть `Out of memory`, добавить swap и не компилировать `.venv`.

### Telegram timeout

Прямой запрос может не работать:

```bash
curl https://api.telegram.org
```

Проверять через Worker:

```bash
curl -sS --connect-timeout 10 --max-time 30 \
"$TELEGRAM_API_BASE_URL/bot$BOT_TOKEN/getMe"
```

### Два бота на одном сервере

Для двух независимых турниров нужны разные:

- папки проекта;
- `BOT_TOKEN`;
- `DB_PATH`;
- `.env`;
- systemd service names.

Cloudflare Worker можно использовать один, если он не ограничен одним токеном.

## 16. Критерии успешного запуска

Проект готов к дальнейшему тестированию/бою, если:

- синтаксис проходит;
- Worker `getMe` возвращает `ok:true`;
- `python main.py` запускается;
- systemd service активен;
- бот отвечает в Telegram;
- прогноз сохраняется;
- `/set_score` завершает матч и обновляет leaderboard;
- `/daily_results` строит корректный отчёт;
- в логах нет повторяющихся tracebacks.
