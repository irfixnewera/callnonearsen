from aiogram import Router

from bot.handlers import correction, diary, photo, profile, start


def setup_routers() -> Router:
    root = Router()
    root.include_router(start.router)
    root.include_router(photo.router)
    root.include_router(diary.router)
    root.include_router(correction.router)
    root.include_router(profile.router)
    return root
