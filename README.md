# Калорийный бот 💛

Telegram-бот: калории и БЖУ по фото еды.  
**Google Gemini Vision** (бесплатный тариф) · мягкий UX · дневник · онбординг.

**Стек:** Python 3.11 · aiogram 3 · SQLAlchemy + aiosqlite · Redis (опционально) · Gemini API

---

## Как получить ключ Gemini (бесплатно)

1. Открой **[Google AI Studio](https://aistudio.google.com/apikey)**  
   (нужен обычный Google-аккаунт).
2. Нажми **Create API key** → выбери проект или создай новый.
3. Скопируй ключ (начинается с `AIza...`).
4. Карта **не нужна**. Это бесплатный тариф.

Рекомендуемые модели (бесплатно):
- `gemini-2.5-flash` — баланс качества и лимитов (по умолчанию)
- `gemini-2.0-flash` — тоже бесплатно
- `gemini-2.5-flash-lite` — больше запросов в день, чуть проще модель

Лимиты смотри в AI Studio → Rate limits (обычно десятки–сотни запросов/день на Flash-Lite).

---

## Быстрый старт локально

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# заполни BOT_TOKEN и GEMINI_API_KEY
python main.py
```

`REDIS_URL` можно оставить пустым.

---

## Деплой на Railway без вложений

1. Залей код на GitHub (без `.env`).
2. [railway.app](https://railway.app) → New Project → Deploy from GitHub.
3. Variables:

```
BOT_TOKEN=...
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash
DATABASE_URL=sqlite+aiosqlite:///./data/bot.db
REDIS_URL=
LOG_LEVEL=INFO
```

4. Start Command уже в `railway.toml`: `python main.py`
5. В логах: `FSM storage: MemoryStorage` и `Polling started`.

### Откуда ключи

| Ключ | Где | Деньги |
|------|-----|--------|
| BOT_TOKEN | [@BotFather](https://t.me/BotFather) | Бесплатно |
| GEMINI_API_KEY | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | **Бесплатно** (лимиты) |
| REDIS_URL | Не нужен | — |

---

## Структура

```
calorie_bot/
├── main.py
├── Procfile / railway.toml
├── .env.example
├── requirements.txt
└── bot/
    ├── config.py
    ├── texts.py
    ├── handlers/          # start, photo, diary, correction, profile
    ├── keyboards/
    ├── services/
    │   └── gemini_vision.py   # Gemini Vision + JSON
    ├── database/
    ├── middlewares/
    ├── states/
    └── utils/
```

## Примеры сообщений

```
🔍 Смотрю на твоё фото...
✨ Почти готово...
🍽 Считаю калории...

Вот что я увидела:

Куриная грудка — 180 г
   198 ккал · Б 37 · Ж 4 · У 0
...
Итого: 393 ккал
Приятного аппетита ✨
[📝 Добавить в дневник] [✏️ Исправить]
```
