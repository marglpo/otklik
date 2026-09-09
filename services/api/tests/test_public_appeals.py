from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import AppEnvironment
from app.core.crypto import ContentCrypto, track_lookup_digest
from app.core.errors import RateLimitError, UnauthorizedError, ValidationError
from app.core.security.tokens import AccessTokenService
from app.db.models import (
    Appeal,
    AppealContent,
    AppealIntakeAnswer,
    AppealRejection,
    Category,
    CrisisContact,
    StatusHistory,
)
from app.db.models.enums import AppealPriority, AppealStatus, ApplicantType, RejectionKind
from app.db.repositories.public_appeals import AppealWithCategory, PublicAppealRepository
from app.main import create_app
from app.modules.appeals.crypto_context import (
    appeal_content_aad,
    crisis_contact_aad,
    intake_answers_aad,
    rejection_reason_aad,
)
from app.modules.appeals.dependencies import (
    get_public_appeal_rate_limiter,
    get_public_appeal_service,
)
from app.modules.appeals.rate_limit import PublicAppealRateLimiter
from app.modules.appeals.schemas import AppealCreateRequest
from app.modules.appeals.service import INVALID_TRACK_MESSAGE, PublicAppealService
from app.modules.appeals.track import (
    TRACK_ALPHABET,
    generate_track_number,
    normalize_track_number,
)
from app.modules.categories.reference_data import STARTER_CATEGORIES
from app.modules.crisis.detector import CrisisRulePattern
from app.modules.crisis.service import CrisisRuleService
from app.scripts.seed_reference_data import seed_categories


class FakePublicRepository:
    def __init__(self, categories: list[Category] | None = None) -> None:
        self.categories = {category.id: category for category in categories or []}
        self.appeals: dict[UUID, Appeal] = {}
        self.contents: dict[UUID, AppealContent] = {}
        self.answers: dict[UUID, AppealIntakeAnswer] = {}
        self.history: dict[UUID, list[StatusHistory]] = {}
        self.contacts: dict[UUID, CrisisContact] = {}
        self.rejections: dict[UUID, AppealRejection] = {}
        self.commits = 0

    async def list_active_categories(self) -> list[Category]:
        return sorted(
            (category for category in self.categories.values() if category.is_active),
            key=lambda category: category.sort_order,
        )

    async def get_category(self, category_id: UUID) -> Category | None:
        return self.categories.get(category_id)

    async def get_category_by_slug(self, slug: str) -> Category | None:
        return next(
            (category for category in self.categories.values() if category.slug == slug),
            None,
        )

    async def add_category(self, category: Category) -> None:
        self.categories[category.id] = category

    async def track_digest_exists(self, digest: bytes) -> bool:
        return any(appeal.track_digest == digest for appeal in self.appeals.values())

    async def add_appeal_bundle(
        self,
        appeal: Appeal,
        content: AppealContent | None,
        intake_answers: AppealIntakeAnswer | None,
        initial_history: StatusHistory,
    ) -> None:
        now = datetime.now(UTC)
        appeal.created_at = now
        appeal.updated_at = now
        initial_history.created_at = now
        self.appeals[appeal.id] = appeal
        if content is not None:
            self.contents[appeal.id] = content
        if intake_answers is not None:
            self.answers[appeal.id] = intake_answers
        self.history[appeal.id] = [initial_history]

    async def get_appeal_by_digest(self, digest: bytes) -> Appeal | None:
        return next(
            (appeal for appeal in self.appeals.values() if appeal.track_digest == digest),
            None,
        )

    async def get_appeal(self, appeal_id: UUID) -> Appeal | None:
        return self.appeals.get(appeal_id)

    async def get_rejection(self, appeal_id: UUID) -> AppealRejection | None:
        return self.rejections.get(appeal_id)

    async def get_appeal_with_category(self, appeal_id: UUID) -> AppealWithCategory | None:
        appeal = self.appeals.get(appeal_id)
        if appeal is None:
            return None
        category = self.categories.get(appeal.category_id) if appeal.category_id else None
        return AppealWithCategory(appeal, category)

    async def list_status_history(self, appeal_id: UUID) -> list[StatusHistory]:
        return self.history.get(appeal_id, [])

    async def upsert_crisis_contact(self, contact: CrisisContact) -> None:
        self.contacts[contact.appeal_id] = contact

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


class NoopPublicRateLimiter:
    async def check(self, kind: str, *, transient_ip: str) -> None:
        del kind, transient_ip


class FakePipeline:
    def __init__(self, store: dict[str, int]) -> None:
        self.store = store
        self.key = ""

    def incr(self, key: str) -> "FakePipeline":
        self.key = key
        return self

    def expire(self, key: str, seconds: int, *, nx: bool) -> "FakePipeline":
        assert key == self.key and seconds > 0 and nx
        return self

    async def execute(self) -> list[int | bool]:
        self.store[self.key] = self.store.get(self.key, 0) + 1
        return [self.store[self.key], True]


class FakeValkey:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    def pipeline(self, *, transaction: bool) -> FakePipeline:
        assert transaction
        return FakePipeline(self.store)


def _category(*, slug: str = "bullying-insults", active: bool = True) -> Category:
    return Category(
        id=uuid4(),
        slug=slug,
        name="Не знаю, как это назвать" if slug == "unsure" else "Буллинг и оскорбления",
        description="Описание",
        is_active=active,
        sort_order=10,
    )


def _service(test_settings, categories: list[Category] | None = None):
    repository = FakePublicRepository(categories)
    service = PublicAppealService(cast(PublicAppealRepository, repository), test_settings)
    return service, repository


def _payload(
    *,
    category_id: UUID | None = None,
    description: str | None = None,
    answers: dict[str, str] | None = None,
    applicant_type: ApplicantType = ApplicantType.STUDENT,
) -> AppealCreateRequest:
    return AppealCreateRequest(
        applicant_type=applicant_type,
        category_id=category_id,
        description=SecretStr(description) if description is not None else None,
        intake_answers=(
            {key: SecretStr(value) for key, value in answers.items()} if answers else None
        ),
    )


def test_track_format_alphabet_and_normalization() -> None:
    tracks = {generate_track_number() for _ in range(100)}
    assert len(tracks) == 100
    for track in tracks:
        assert track.startswith("ОТК-") and len(track) == 13
        significant = track.replace("ОТК-", "").replace("-", "")
        assert len(significant) == 8
        assert set(significant) <= set(TRACK_ALPHABET)
        assert not set(significant) & set("0O1ILl")
    assert normalize_track_number("  otk abcd 2345 ") == "ОТК-ABCD-2345"
    assert normalize_track_number("отк—abcd—2345") == "ОТК-ABCD-2345"
    with pytest.raises(ValueError):
        normalize_track_number("ОТК-OBCD-2345")


async def test_category_only_creation_stores_digest_and_safe_defaults(test_settings) -> None:
    category = _category()
    service, repository = _service(test_settings, [category])

    result = await service.create_appeal(_payload(category_id=category.id))
    appeal = next(iter(repository.appeals.values()))

    assert appeal.track_digest == track_lookup_digest(
        test_settings.track_hmac_secret.get_secret_value(), result.response.track_number
    )
    assert result.response.track_number.encode() not in repr(appeal.__dict__).encode()
    assert appeal.status is AppealStatus.NEW
    assert appeal.priority is AppealPriority.STANDARD
    assert appeal.id not in repository.contents
    assert len(repository.history[appeal.id]) == 1


async def test_free_text_and_answers_are_encrypted_separately(test_settings) -> None:
    service, repository = _service(test_settings)
    description = "Мне нужна помощь с ситуацией"
    answers = {"where": "в школе", "duration": "две недели"}

    result = await service.create_appeal(_payload(description=description, answers=answers))
    appeal = next(iter(repository.appeals.values()))
    content = repository.contents[appeal.id]
    intake = repository.answers[appeal.id]
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())

    assert description.encode() not in content.encrypted_content
    assert crypto.decrypt_text(
        content.encrypted_content, aad=appeal_content_aad(appeal.id)
    ) == description
    assert crypto.decrypt_json(
        intake.encrypted_payload, aad=intake_answers_aad(appeal.id)
    ) == answers
    assert result.response.status is AppealStatus.NEW


async def test_unsure_category_requires_free_text(test_settings) -> None:
    category = _category(slug="unsure")
    service, _repository = _service(test_settings, [category])
    with pytest.raises(ValidationError):
        await service.create_appeal(_payload(category_id=category.id))


async def test_crisis_detection_does_not_escalate_priority(test_settings) -> None:
    service, repository = _service(test_settings)
    result = await service.create_appeal(_payload(description="Мне угрожают убить"))
    appeal = next(iter(repository.appeals.values()))
    assert appeal.crisis_flag is True
    assert appeal.priority is AppealPriority.STANDARD
    assert result.response.show_crisis_support is True


async def test_appeal_creation_uses_loaded_persistent_crisis_rules(test_settings) -> None:
    class FakeCrisisRules:
        async def active_patterns(self) -> list[CrisisRulePattern]:
            return [CrisisRulePattern.from_phrase("маркер только из базы")]

    repository = FakePublicRepository()
    service = PublicAppealService(
        cast(PublicAppealRepository, repository),
        test_settings,
        cast(CrisisRuleService, FakeCrisisRules()),
    )

    await service.create_appeal(_payload(description="Есть маркер-только-из-базы"))

    appeal = next(iter(repository.appeals.values()))
    assert appeal.crisis_flag is True
    assert appeal.priority is AppealPriority.STANDARD


async def test_crisis_contact_is_encrypted_and_isolated(test_settings) -> None:
    service, repository = _service(test_settings)
    await service.create_appeal(_payload(description="Хочу умереть"))
    appeal = next(iter(repository.appeals.values()))
    contact_value = "Связаться через доверенного взрослого"

    await service.save_crisis_contact(appeal.id, contact_value)
    contact = repository.contacts[appeal.id]
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())

    assert contact_value.encode() not in contact.encrypted_contact
    assert crypto.decrypt_text(
        contact.encrypted_contact, aad=crisis_contact_aad(appeal.id)
    ) == contact_value
    assert "contact" not in Appeal.__table__.columns


async def test_track_access_succeeds_and_invalid_is_generic(test_settings) -> None:
    service, _repository = _service(test_settings)
    created = await service.create_appeal(_payload(description="Нужна помощь"))
    accessed = await service.access_appeal(created.response.track_number.lower())
    assert service.decode_access_token(accessed.access_token) == accessed.appeal_id

    messages = []
    for invalid in ("bad", "ОТК-2222-2223"):
        with pytest.raises(UnauthorizedError) as error:
            await service.access_appeal(invalid)
        messages.append(error.value.message)
    assert messages == [INVALID_TRACK_MESSAGE, INVALID_TRACK_MESSAGE]


async def test_current_response_contains_only_applicant_safe_fields(test_settings) -> None:
    category = _category()
    service, _repository = _service(test_settings, [category])
    created = await service.create_appeal(
        _payload(category_id=category.id, description="Нужна помощь")
    )
    appeal_id = service.decode_access_token(created.access_token)
    response = await service.current_appeal(appeal_id)
    fields = set(response.model_dump())

    assert fields == {
        "applicant_type",
        "category",
        "status",
        "status_text",
        "crisis_flag",
        "show_crisis_support",
        "crisis_support_resources",
        "created_at",
        "updated_at",
        "timeline",
        "rejection_reason",
    }
    serialized = response.model_dump_json()
    assert all(
        forbidden not in serialized
        for forbidden in ("track_digest", "assigned_expert", "staff_user", "internal_notes")
    )


async def test_current_response_decrypts_only_applicant_visible_rejection(test_settings) -> None:
    service, repository = _service(test_settings)
    created = await service.create_appeal(_payload(description="Нужна помощь"))
    appeal_id = service.decode_access_token(created.access_token)
    repository.appeals[appeal_id].status = AppealStatus.REJECTED
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())
    repository.rejections[appeal_id] = AppealRejection(
        appeal_id=appeal_id,
        kind=RejectionKind.OUTSIDE_COMPETENCE,
        encrypted_reason=crypto.encrypt_text(
            "Пожалуйста, обратитесь в профильную службу.",
            aad=rejection_reason_aad(appeal_id),
        ),
        key_version=crypto.key_version,
    )

    response = await service.current_appeal(appeal_id)

    assert response.rejection_reason == "Пожалуйста, обратитесь в профильную службу."


def test_applicant_access_token_cannot_authenticate_as_staff(test_settings) -> None:
    service, _repository = _service(test_settings)
    applicant_token = service._access_tokens.issue(uuid4())
    with pytest.raises(UnauthorizedError):
        AccessTokenService(test_settings).decode(applicant_token)


async def test_public_rate_limit_uses_only_hmac_network_key(test_settings) -> None:
    valkey = FakeValkey()
    settings = test_settings.model_copy(update={"track_access_rate_limit_attempts": 2})
    limiter = PublicAppealRateLimiter(cast(object, valkey), settings)
    await limiter.check("track-access", transient_ip="203.0.113.7")
    await limiter.check("track-access", transient_ip="203.0.113.7")
    with pytest.raises(RateLimitError) as error:
        await limiter.check("track-access", transient_ip="203.0.113.7")

    assert error.value.status_code == 429
    stored_key = next(iter(valkey.store))
    assert "203.0.113.7" not in stored_key
    assert stored_key.startswith("public:track-access:network:")


async def test_public_api_sets_secure_httponly_cookie_in_production(test_settings) -> None:
    category = _category()
    production_settings = test_settings.model_copy(
        update={"app_env": AppEnvironment.PRODUCTION, "applicant_access_ttl_minutes": 30}
    )
    service, _repository = _service(production_settings, [category])
    app = create_app(production_settings)
    app.dependency_overrides[get_public_appeal_service] = lambda: service
    app.dependency_overrides[get_public_appeal_rate_limiter] = lambda: NoopPublicRateLimiter()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/public/appeals",
            json={"applicant_type": "student", "category_id": str(category.id)},
        )

    assert response.status_code == 201
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
    assert "Path=/api/v1/public/appeals" in cookie


async def test_reference_includes_unsure_category_and_four_optional_questions(
    test_settings,
) -> None:
    unsure = _category(slug="unsure")
    service, _repository = _service(test_settings, [unsure])
    response = await service.public_reference()
    assert response.categories[0].name == "Не знаю, как это назвать"
    assert response.categories[0].requires_description is True
    assert len(response.intake_questions) == 4
    assert all(question.optional for question in response.intake_questions)


async def test_reference_seed_is_idempotent() -> None:
    repository = FakePublicRepository()
    first = await seed_categories(cast(PublicAppealRepository, repository))
    second = await seed_categories(cast(PublicAppealRepository, repository))

    assert first == (len(STARTER_CATEGORIES), 0)
    assert second == (0, 0)
    assert len(repository.categories) == len(STARTER_CATEGORIES)
