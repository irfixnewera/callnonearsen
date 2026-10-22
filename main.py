"""
Точка входа бота.
Запуск: python main.py

На Railway / любом хосте:
- REDIS_URL пустой → MemoryStorage (бесплатно, FSM сбрасывается при рестарте)
- REDIS_URL задан → RedisStorage
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import BaseStorage

from bot.config import get_settings
from bot.database.session import init_db
from bot.handlers import setup_routers
from bot.middlewares.db import DbSessionMiddleware


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.INFO)


def build_storage(redis_url: str) -> tuple[BaseStorage, object | None]:
    """Возвращает (storage, redis_client_or_None)."""
    if redis_url and redis_url.strip():
        from aiogram.fsm.storage.redis import RedisStorage
        from redis.asyncio import Redis

        redis = Redis.from_url(redis_url)
        return RedisStorage(redis=redis), redis

    return MemoryStorage(), None


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    logger = logging.getLogger(__name__)
    logger.info("Starting calorie bot...")

    # Создаём папку data, если её нет (для SQLite)
    Path("data").mkdir(exist_ok=True)

    await init_db()
    logger.info("Database initialized (%s)", settings.database_url)

    storage, redis = build_storage(settings.redis_url)
    if redis is None:
        logger.info("FSM storage: MemoryStorage (no Redis)")
    else:
        logger.info("FSM storage: Redis")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=storage)

    dp.update.middleware(DbSessionMiddleware())
    dp.include_router(setup_routers())

    try:
        logger.info("Polling started")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        if redis is not None:
            await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
