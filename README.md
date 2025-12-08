# Telegram Group Bot — python-telegram-bot (20+)

Коротко: готовый Telegram-бот на Python (python-telegram-bot 20+) для чата — хранит анкеты и репорты в SQLite.

Запуск
1) Клонируйте репозиторий и перейдите в каталог проекта.
2) Создайте виртуальное окружение и установите зависимости:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3) Создайте `.env` на основе примера и вставьте токен бота и, при желании, список admin ids:

```bash
cp .env.example .env
# отредактируйте .env
```

4) Запустите бота:

```bash
python main.py
```

Примеры команд/кнопок
- /start — приветствие и показ ReplyKeyboard
- Информация о пользователях — показывает одно сообщение «Список анкет — выберите пользователя:» и под ним inline-кнопки `view:<username>` для каждого пользователя
- Новая анкета — запускает диалог для создания анкеты. При отсутствии username сообщит об ошибке.
- Новая анкета — запускает диалог для создания анкеты. При отсутствии username сообщит об ошибке. Анкеты, добавленные пользователями, сначала отправляются на модерацию (status = pending) владельцу админ-панели (SUPER_ADMIN_ID). Админ может принять или отклонить анкету — после принятия статус станет approved и анкета появится в общем списке.
- Репорт — выбор категории (inline) → ввод причины → сохранение и уведомление админов
- Информация о чате — basic chat info
- /export_csv — экспорт CSV всех анкеты (только admin)

Callback data (префиксы):
- `view:<username>` — показать карточку пользователя
- `edit:<username>` — начать редактирование (admin)
- `delete:<username>` — запрос подтверждения удаления (admin)
- `delete_confirm:<username>` — подтвердить удаление
- `back:users`, `back:menu`, `back:add_new` — навигация
- `report:<category>` — выбор категории репорта
- `new:confirm`, `new:cancel` — подтверждение/отмена новой анкеты

SQL схема (таблицы)

profiles:
```
id INTEGER PRIMARY KEY AUTOINCREMENT
username TEXT UNIQUE NOT NULL
age INTEGER NULL
name TEXT NULL
country TEXT NULL
city TEXT NULL
timezone TEXT NULL
tz_offset INTEGER NULL
languages TEXT NULL
note TEXT NULL
added_by TEXT
added_by_id INTEGER  -- optional: Telegram user id who submitted
status TEXT          -- pending|approved|rejected
added_at TEXT (ISO8601)
```

reports:
```
id INTEGER PRIMARY KEY AUTOINCREMENT
reporter_id INTEGER
reporter_username TEXT
category TEXT
target_identifier TEXT
reason TEXT
attachments TEXT
created_at TEXT (ISO8601)
```

Seed
- При первом запуске в БД автоматически добавляются 9 профилей (см. код `db.py`).

Безопасность и поведение
- Токен берётся из `TELEGRAM_BOT_TOKEN` (через `config.py`). Никогда не логируйте токен.
- Команды админа ограничены `ADMIN_IDS` (переменная окружения `ADMIN_IDS`, разделённые запятыми).
- Логи: INFO/ERROR; не логировать персональные данные без флага `ADMIN`.

Ограничения / компромиссы
- Парсер анкеты — простой эвристический (регекспы) и не претендует на 100% правильность. При отсутствии поля бот запрашивает только недостающую часть.
- В интерфейсе использую удаление/редактирование через простые inline confirm/набор новых данных (без сложных форм).

Файлы
- `main.py` — точка входа и регистрация обработчиков
- `handlers.py` — реализованы все обработчики (menu/users/new profile/report/chat/admin)
- `keyboards.py` — reply & inline keyboards
- `db.py` — SQLite wrapper + seed
- `config.py` — читать TELEGRAM_BOT_TOKEN и ADMIN_IDS
- `utils.py` — парсер анкеты + форматирование
- `templates/messages.py` — тексты сообщений
- `requirements.txt`, `.env.example`
