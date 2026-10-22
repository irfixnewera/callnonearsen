from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import DiaryEntry, User


class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, telegram_id: int, name: str | None = None) -> User:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = User(telegram_id=telegram_id, name=name)
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
        return user

    async def mark_onboarding_done(self, user: User) -> None:
        user.onboarding_done = True
        await self.session.commit()

    async def update_name(self, user: User, name: str) -> None:
        user.name = name
        await self.session.commit()

    async def update_goal(self, user: User, goal: int | None) -> None:
        user.calorie_goal = goal
        await self.session.commit()


class DiaryRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_entry(
        self,
        user_id: int,
        items_json: str,
        calories: int,
        protein: int,
        fat: int,
        carbs: int,
        comment: str | None = None,
    ) -> DiaryEntry:
        entry = DiaryEntry(
            user_id=user_id,
            items_json=items_json,
            calories=calories,
            protein=protein,
            fat=fat,
            carbs=carbs,
            comment=comment,
        )
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def delete_entry(self, entry_id: int, user_id: int) -> bool:
        result = await self.session.execute(
            select(DiaryEntry).where(
                and_(DiaryEntry.id == entry_id, DiaryEntry.user_id == user_id)
            )
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            return False
        await self.session.delete(entry)
        await self.session.commit()
        return True

    async def get_entries_for_day(
        self, user_id: int, day: datetime
    ) -> list[DiaryEntry]:
        start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        result = await self.session.execute(
            select(DiaryEntry)
            .where(
                and_(
                    DiaryEntry.user_id == user_id,
                    DiaryEntry.created_at >= start,
                    DiaryEntry.created_at < end,
                )
            )
            .order_by(DiaryEntry.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_entries_for_period(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[DiaryEntry]:
        result = await self.session.execute(
            select(DiaryEntry)
            .where(
                and_(
                    DiaryEntry.user_id == user_id,
                    DiaryEntry.created_at >= start,
                    DiaryEntry.created_at < end,
                )
            )
            .order_by(DiaryEntry.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_day_totals(
        self, user_id: int, day: datetime
    ) -> tuple[int, int, int, int]:
        """Возвращает (calories, protein, fat, carbs)."""
        start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        result = await self.session.execute(
            select(
                func.coalesce(func.sum(DiaryEntry.calories), 0),
                func.coalesce(func.sum(DiaryEntry.protein), 0),
                func.coalesce(func.sum(DiaryEntry.fat), 0),
                func.coalesce(func.sum(DiaryEntry.carbs), 0),
            ).where(
                and_(
                    DiaryEntry.user_id == user_id,
                    DiaryEntry.created_at >= start,
                    DiaryEntry.created_at < end,
                )
            )
        )
        row = result.one()
        return int(row[0]), int(row[1]), int(row[2]), int(row[3])
