from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Appeal,
    AppealContent,
    AppealIntakeAnswer,
    AppealRejection,
    Attachment,
    Category,
    CrisisContact,
    StatusHistory,
)


@dataclass(frozen=True, slots=True)
class AppealWithCategory:
    appeal: Appeal
    category: Category | None


class PublicAppealRepository:
    """Concrete persistence operations for the anonymous appeal flow."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active_categories(self) -> list[Category]:
        result = await self._session.scalars(
            select(Category)
            .where(Category.is_active.is_(True))
            .order_by(Category.sort_order, Category.name)
        )
        return list(result)

    async def get_category(self, category_id: UUID) -> Category | None:
        return await self._session.get(Category, category_id)

    async def get_category_by_slug(self, slug: str) -> Category | None:
        return await self._session.scalar(select(Category).where(Category.slug == slug))

    async def add_category(self, category: Category) -> None:
        self._session.add(category)
        await self._session.flush()

    async def track_digest_exists(self, digest: bytes) -> bool:
        statement = select(Appeal.id).where(Appeal.track_digest == digest).limit(1)
        return await self._session.scalar(statement) is not None

    async def add_appeal_bundle(
        self,
        appeal: Appeal,
        content: AppealContent | None,
        intake_answers: AppealIntakeAnswer | None,
        initial_history: StatusHistory,
    ) -> None:
        records = [appeal, initial_history]
        if content is not None:
            records.append(content)
        if intake_answers is not None:
            records.append(intake_answers)
        self._session.add_all(records)
        await self._session.flush()

    async def get_appeal_by_digest(self, digest: bytes) -> Appeal | None:
        return await self._session.scalar(select(Appeal).where(Appeal.track_digest == digest))

    async def get_appeal(self, appeal_id: UUID) -> Appeal | None:
        return await self._session.get(Appeal, appeal_id)

    async def get_rejection(self, appeal_id: UUID) -> AppealRejection | None:
        return await self._session.get(AppealRejection, appeal_id)

    async def get_appeal_with_category(self, appeal_id: UUID) -> AppealWithCategory | None:
        result = await self._session.execute(
            select(Appeal, Category)
            .outerjoin(Category, Appeal.category_id == Category.id)
            .where(Appeal.id == appeal_id)
        )
        row = result.one_or_none()
        return AppealWithCategory(row[0], row[1]) if row is not None else None

    async def list_status_history(self, appeal_id: UUID) -> list[StatusHistory]:
        result = await self._session.scalars(
            select(StatusHistory)
            .where(StatusHistory.appeal_id == appeal_id)
            .order_by(StatusHistory.created_at, StatusHistory.id)
        )
        return list(result)

    async def upsert_crisis_contact(self, contact: CrisisContact) -> None:
        existing = await self._session.get(CrisisContact, contact.appeal_id)
        if existing is None:
            self._session.add(contact)
        else:
            existing.encrypted_contact = contact.encrypted_contact
            existing.key_version = contact.key_version
        await self._session.flush()

    async def lock_appeal(self, appeal_id: UUID) -> Appeal | None:
        return await self._session.scalar(
            select(Appeal).where(Appeal.id == appeal_id).with_for_update()
        )

    async def count_attachments(self, appeal_id: UUID) -> int:
        count = await self._session.scalar(
            select(func.count()).select_from(Attachment).where(Attachment.appeal_id == appeal_id)
        )
        return int(count or 0)

    async def add_attachment(self, attachment: Attachment) -> None:
        self._session.add(attachment)
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
