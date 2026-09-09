from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import StaffRole, string_enum


class StaffUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Internal staff identity; anonymous applicants never have user records."""

    __tablename__ = "staff_users"
    __table_args__ = (
        UniqueConstraint("login", name="staff_users_login"),
        CheckConstraint(
            "login = lower(btrim(login))", name="staff_users_login_normalized"
        ),
    )

    login: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[StaffRole] = mapped_column(
        string_enum(StaffRole, name="staff_role"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)


class ExpertProfile(Base):
    __tablename__ = "expert_profiles"
    __table_args__ = (
        CheckConstraint(
            "max_active_appeals > 0", name="expert_profiles_positive_capacity"
        ),
    )

    staff_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_users.id", ondelete="CASCADE"), primary_key=True
    )
    max_active_appeals: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, server_default=text("10")
    )


class ExpertGroupMembership(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "expert_group_memberships"
    __table_args__ = (
        UniqueConstraint(
            "expert_id", "specialist_group_id", name="expert_group_memberships_pair"
        ),
    )

    expert_id: Mapped[UUID] = mapped_column(
        ForeignKey("expert_profiles.staff_user_id", ondelete="CASCADE"), nullable=False
    )
    specialist_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("specialist_groups.id", ondelete="CASCADE"), nullable=False
    )
