"""
Точка входа бота.
Запуск: python main.py

Render (бесплатный Web Service):
- слушает PORT (health-check), параллельно polling Telegram
- чтобы не засыпал: пингуй URL раз в 10–14 мин (cron-job.org)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage

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
    if redis_url and redis_url.strip():
        from aiogram.fsm.storage.redis import RedisStorage
        from redis.asyncio import Redis

        redis = Redis.from_url(redis_url)
        return RedisStorage(redis=redis), redis
    return MemoryStorage(), None


def start_health_server(port: int) -> None:
    """Мини-HTTP для Render: отвечает 200 на любой путь."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = HTTPServer(("0.0.0.0", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logging.getLogger(__name__).info("Health server on port %s", port)


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting calorie bot...")

    # Render / любой PaaS: если задан PORT — поднимаем health endpoint
    port_str = os.getenv("PORT")
    if port_str:
        try:
            start_health_server(int(port_str))
        except Exception as exc:
            logger.warning("Health server failed: %s", exc)

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
