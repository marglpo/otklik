from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import TimestampMixin, UUIDPrimaryKeyMixin


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("slug", name="categories_slug"),
        CheckConstraint("slug = lower(btrim(slug))", name="categories_slug_normalized"),
        CheckConstraint("sort_order >= 0", name="categories_nonnegative_sort_order"),
    )

    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )


class SpecialistGroup(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "specialist_groups"
    __table_args__ = (
        UniqueConstraint("slug", name="specialist_groups_slug"),
        CheckConstraint(
            "slug = lower(btrim(slug))", name="specialist_groups_slug_normalized"
        ),
    )

    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )


class CategoryGroupRule(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "category_group_rules"
    __table_args__ = (
        UniqueConstraint(
            "category_id", "specialist_group_id", name="category_group_rules_pair"
        ),
    )

    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    specialist_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("specialist_groups.id", ondelete="CASCADE"), nullable=False
    )
