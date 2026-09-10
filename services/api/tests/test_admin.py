from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.email import SMTPMailer
from app.core.errors import InfrastructureError, UnauthorizedError, ValidationError
from app.core.security.passwords import verify_password
from app.db.models import (
    ApplicantTypeConfig,
    AuditLog,
    CrisisRule,
    ExpertProfile,
    StaffInvitation,
    StaffSession,
    StaffUser,
)
from app.db.models.enums import ApplicantTone, StaffInvitationPurpose, StaffRole
from app.db.repositories.admin import AdminRepository
from app.main import create_app
from app.modules.admin.dependencies import get_admin_service
from app.modules.admin.schemas import (
    ApplicantTypeRequest,
    ApplicantTypeUpdate,
    CrisisRuleRequest,
    CrisisRuleTestRequest,
    IntakeQuestionRequest,
    StaffCreateRequest,
    StaffUpdateRequest,
)
from app.modules.admin.service import AdminService
from app.modules.auth.dependencies import get_auth_service


class FakeMailer:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[dict[str, object]] = []

    async def send_staff_setup(self, **kwargs) -> None:
        if self.fail:
            raise InfrastructureError("SMTP is not configured.")
        self.messages.append(kwargs)


class FakeAdminRepository:
    def __init__(self) -> None:
        self.staff: dict[UUID, StaffUser] = {}
        self.profiles: dict[UUID, ExpertProfile] = {}
        self.sessions: list[StaffSession] = []
        self.invitations: list[StaffInvitation] = []
        self.audits: list[AuditLog] = []
        self.applicant_types: dict[UUID, ApplicantTypeConfig] = {}
        self.crisis_rules: dict[UUID, CrisisRule] = {}
        self.commits = 0

    async def list_staff(self):
        return list(self.staff.values())

    async def get_staff(self, staff_id):
        return self.staff.get(staff_id)

    async def get_staff_by_login(self, login):
        return next((item for item in self.staff.values() if item.login == login), None)

    async def get_staff_by_email(self, email):
        return next((item for item in self.staff.values() if item.email == email), None)

    async def get_expert_profile(self, staff_id):
        return self.profiles.get(staff_id)

    async def list_membership_group_ids(self, expert_id):
        del expert_id
        return []

    async def active_workload(self, expert_id):
        del expert_id
        return 0

    def _store(self, record):
        now = datetime.now(UTC)
        if isinstance(record, StaffUser):
            record.created_at = record.created_at or now
            record.updated_at = record.updated_at or now
            self.staff[record.id] = record
        elif isinstance(record, ExpertProfile):
            self.profiles[record.staff_user_id] = record
        elif isinstance(record, StaffInvitation):
            record.created_at = record.created_at or now
            self.invitations.append(record)
        elif isinstance(record, AuditLog):
            record.created_at = record.created_at or now
            self.audits.append(record)
        elif isinstance(record, ApplicantTypeConfig):
            record.created_at = record.created_at or now
            record.updated_at = record.updated_at or now
            self.applicant_types[record.id] = record
        elif isinstance(record, CrisisRule):
            record.created_at = record.created_at or now
            record.updated_at = record.updated_at or now
            self.crisis_rules[record.id] = record

    async def add(self, record):
        self._store(record)

    async def add_all(self, records):
        for record in records:
            self._store(record)

    async def add_audit(self, audit):
        self._store(audit)

    async def revoke_sessions(self, staff_id, now):
        for session in self.sessions:
            if session.staff_user_id == staff_id and session.revoked_at is None:
                session.revoked_at = now

    async def consume_open_invitations(self, staff_id, now):
        for invitation in self.invitations:
            if invitation.staff_user_id == staff_id and invitation.consumed_at is None:
                invitation.consumed_at = now

    async def invitation_for_update(self, digest):
        return next((item for item in self.invitations if item.token_digest == digest), None)

    async def list_applicant_types(self, *, active_only=False):
        values = list(self.applicant_types.values())
        return [item for item in values if item.is_active] if active_only else values

    async def get_applicant_type(self, item_id):
        return self.applicant_types.get(item_id)

    async def get_applicant_type_by_code(self, code):
        return next((item for item in self.applicant_types.values() if item.code == code), None)

    async def list_crisis_rules(self, *, active_only=False):
        values = list(self.crisis_rules.values())
        return [item for item in values if item.is_active] if active_only else values

    async def get_crisis_rule(self, item_id):
        return self.crisis_rules.get(item_id)

    async def crisis_rule_by_normalized(self, normalized):
        return next(
            (item for item in self.crisis_rules.values() if item.normalized_phrase == normalized),
            None,
        )

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None


def _service(test_settings, *, fail_mail=False):
    repository = FakeAdminRepository()
    mailer = FakeMailer(fail=fail_mail)
    service = AdminService(
        cast(AdminRepository, repository), test_settings, cast(SMTPMailer, mailer)
    )
    return service, repository, mailer


def _staff_payload(*, role=StaffRole.OPERATOR, email="new@example.org"):
    return StaffCreateRequest(
        login=" New_Staff ",
        email=email,
        display_name="Новый сотрудник",
        role=role,
        public_specialist_label="Психолог" if role is StaffRole.EXPERT else None,
        max_active_appeals=7,
    )


async def test_staff_invitation_stores_only_digest_and_creates_expert_profile(
    test_settings,
) -> None:
    service, repository, mailer = _service(test_settings)
    result = await service.create_staff(_staff_payload(role=StaffRole.EXPERT), admin_id=uuid4())

    staff = result.staff
    invitation = repository.invitations[0]
    raw_token = cast(str, mailer.messages[0]["raw_token"])
    assert staff.login == "new_staff"
    assert staff.password_configured is False
    assert staff.public_specialist_label == "Психолог"
    assert staff.max_active_appeals == 7
    assert invitation.token_digest != raw_token.encode()
    assert raw_token not in repr(invitation)
    assert len(invitation.token_digest) == 32
    assert "raw_token" not in (repository.audits[-1].metadata_json or {})


async def test_password_setup_is_one_time_argon2_and_reset_revokes_sessions(
    test_settings,
) -> None:
    service, repository, mailer = _service(test_settings)
    created = await service.create_staff(_staff_payload(), admin_id=uuid4())
    staff = repository.staff[created.staff.id]
    session = StaffSession(
        id=uuid4(),
        staff_user_id=staff.id,
        refresh_token_digest=b"s" * 32,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    repository.sessions.append(session)
    token = cast(str, mailer.messages[0]["raw_token"])

    await service.setup_password(token, "a secure password 2026")
    assert staff.password_hash is not None
    assert staff.password_hash != "a secure password 2026"
    assert verify_password("a secure password 2026", staff.password_hash)
    assert session.revoked_at is not None
    with pytest.raises(UnauthorizedError):
        await service.setup_password(token, "another secure password")


async def test_expired_invitation_is_rejected(test_settings) -> None:
    service, repository, mailer = _service(test_settings)
    await service.create_staff(_staff_payload(), admin_id=uuid4())
    repository.invitations[0].expires_at = datetime.now(UTC) - timedelta(seconds=1)
    with pytest.raises(UnauthorizedError):
        await service.setup_password(
            cast(str, mailer.messages[0]["raw_token"]), "a secure password 2026"
        )


async def test_smtp_failure_is_controlled_after_staff_is_saved(test_settings) -> None:
    service, repository, _mailer = _service(test_settings, fail_mail=True)
    result = await service.create_staff(_staff_payload(), admin_id=uuid4())
    assert result.email_sent is False
    assert result.staff.id in repository.staff
    assert repository.invitations


async def test_changing_expert_role_hides_expert_only_configuration(test_settings) -> None:
    service, _repository, _mailer = _service(test_settings)
    created = await service.create_staff(
        _staff_payload(role=StaffRole.EXPERT), admin_id=uuid4()
    )
    updated = await service.update_staff(
        created.staff.id,
        StaffUpdateRequest(role=StaffRole.OPERATOR),
        admin_id=uuid4(),
    )
    assert updated.role is StaffRole.OPERATOR
    assert updated.public_specialist_label is None
    assert updated.max_active_appeals is None
    assert updated.group_ids == []


async def test_changing_operator_to_expert_requires_and_creates_profile(test_settings) -> None:
    service, repository, _mailer = _service(test_settings)
    created = await service.create_staff(_staff_payload(), admin_id=uuid4())
    with pytest.raises(ValidationError, match="specialization"):
        await service.update_staff(
            created.staff.id,
            StaffUpdateRequest(role=StaffRole.EXPERT),
            admin_id=uuid4(),
        )
    updated = await service.update_staff(
        created.staff.id,
        StaffUpdateRequest(
            role=StaffRole.EXPERT,
            public_specialist_label="Юрист",
            max_active_appeals=6,
        ),
        admin_id=uuid4(),
    )
    assert updated.role is StaffRole.EXPERT
    assert updated.public_specialist_label == "Юрист"
    assert repository.profiles[created.staff.id].max_active_appeals == 6


async def test_applicant_type_configuration_is_orderable_and_archivable(test_settings) -> None:
    service, repository, _mailer = _service(test_settings)
    created = await service.create_applicant_type(
        ApplicantTypeRequest(
            code="graduate",
            label="Выпускник",
            tone=ApplicantTone.FORMAL,
            sort_order=5,
        ),
        admin_id=uuid4(),
    )
    updated = await service.update_applicant_type(
        created.id,
        payload=ApplicantTypeUpdate(is_active=False, sort_order=50),
        admin_id=uuid4(),
    )
    assert updated.is_active is False
    assert updated.sort_order == 50
    assert repository.applicant_types[created.id].code == "graduate"


def test_choice_question_schema_requires_safe_options() -> None:
    with pytest.raises(ValueError):
        IntakeQuestionRequest(
            code="unsafe-choice",
            label="Выберите",
            field_type="single_choice",
            options=[],
        )
    valid = IntakeQuestionRequest(
        code="safe-choice",
        label="Выберите",
        field_type="single_choice",
        options=["Первый", "Второй"],
    )
    assert valid.options == ["Первый", "Второй"]


async def test_crisis_tester_uses_active_rules_without_persisting_input(test_settings) -> None:
    service, repository, _mailer = _service(test_settings)
    rule = await service.create_crisis_rule(
        CrisisRuleRequest(phrase="не хочу жить", allow_compact_match=True),
        admin_id=uuid4(),
    )
    audits_before = len(repository.audits)
    result = await service.test_crisis_phrase("НЕ-ХОЧУ-ЖИТЬ")
    assert result.crisis_detected is True
    assert result.matched_rules[0].id == rule.id
    assert len(repository.audits) == audits_before
    assert "НЕ-ХОЧУ-ЖИТЬ" not in repr(repository.__dict__)


class FakeAuthService:
    def __init__(self, roles: dict[str, StaffRole]) -> None:
        self.roles = roles

    async def authenticate_access_token(self, token: str) -> StaffUser:
        role = self.roles.get(token)
        if role is None:
            raise UnauthorizedError()
        return StaffUser(
            id=uuid4(),
            login=f"{role.value}_staff",
            password_hash="unused",
            role=role,
            is_active=True,
            display_name=role.value,
        )


class FakeAdminService:
    async def list_staff(self):
        return []


async def test_admin_routes_enforce_exact_admin_role(test_settings) -> None:
    app = create_app(test_settings)
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService(
        {"operator": StaffRole.OPERATOR, "expert": StaffRole.EXPERT, "admin": StaffRole.ADMIN}
    )
    app.dependency_overrides[get_admin_service] = lambda: FakeAdminService()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/v1/admin/staff")).status_code == 401
        for token in ("operator", "expert"):
            response = await client.get(
                "/api/v1/admin/staff", headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 403
        response = await client.get(
            "/api/v1/admin/staff", headers={"Authorization": "Bearer admin"}
        )
        assert response.status_code == 200


def test_crisis_test_payload_redacts_input() -> None:
    payload = CrisisRuleTestRequest(text="sensitive test input")
    assert "sensitive test input" not in repr(payload)


async def test_unconfigured_smtp_adapter_fails_only_when_sending(test_settings) -> None:
    mailer = SMTPMailer(test_settings)
    with pytest.raises(InfrastructureError, match="SMTP is not configured"):
        await mailer.send_staff_setup(
            recipient="staff@example.org",
            login="staff",
            role=StaffRole.OPERATOR,
            raw_token="secret-token",
            purpose=StaffInvitationPurpose.INVITATION,
        )
