from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.crypto import ContentCrypto, track_lookup_digest
from app.core.errors import (
    ForbiddenError,
    InfrastructureError,
    UnauthorizedError,
    ValidationError,
)
from app.core.security.appeal_access import AppealAccessTokenService
from app.db.models import (
    Appeal,
    AppealContent,
    AppealIntakeAnswer,
    Category,
    CrisisContact,
    StatusHistory,
)
from app.db.models.enums import AppealPriority, AppealStatus
from app.db.repositories.public_appeals import PublicAppealRepository
from app.modules.appeals.crypto_context import (
    appeal_content_aad,
    crisis_contact_aad,
    intake_answers_aad,
    rejection_reason_aad,
)
from app.modules.appeals.schemas import (
    AppealCreatedResponse,
    AppealCreateRequest,
    CategoryPublic,
    CrisisSupportResourcePublic,
    CurrentAppealResponse,
    IntakeQuestionPublic,
    PublicReferenceResponse,
    StatusTimelineItem,
)
from app.modules.appeals.status import applicant_status_text
from app.modules.appeals.track import generate_track_number, normalize_track_number
from app.modules.categories.reference_data import (
    INTAKE_QUESTIONS,
    UNKNOWN_CATEGORY_SLUG,
)
from app.modules.crisis.detector import CrisisDetector
from app.modules.crisis.service import CrisisRuleService

INVALID_TRACK_MESSAGE = "The track number is invalid or unavailable."
_INVALID_TRACK_PLACEHOLDER = "ОТК-2222-2222"


@dataclass(frozen=True, slots=True)
class AppealAccessResult:
    appeal_id: UUID
    access_token: str


@dataclass(frozen=True, slots=True)
class CreatedAppealResult:
    response: AppealCreatedResponse
    access_token: str


class PublicAppealService:
    def __init__(
        self,
        repository: PublicAppealRepository,
        settings: Settings,
        crisis_rule_service: CrisisRuleService | None = None,
    ) -> None:
        content_key = settings.content_encryption_key
        track_secret = settings.track_hmac_secret
        if content_key is None or not content_key.get_secret_value():
            raise InfrastructureError("Sensitive-content encryption is not configured.")
        if track_secret is None or not track_secret.get_secret_value():
            raise InfrastructureError("Track lookup is not configured.")
        self._repository = repository
        self._settings = settings
        self._crypto = ContentCrypto(content_key.get_secret_value())
        self._track_secret = track_secret.get_secret_value()
        self._access_tokens = AppealAccessTokenService(settings)
        self._crisis_rules = crisis_rule_service

    async def public_reference(self) -> PublicReferenceResponse:
        categories = await self._repository.list_active_categories()
        return PublicReferenceResponse(
            categories=[self._category_public(category) for category in categories],
            intake_questions=[
                IntakeQuestionPublic(
                    id=question.id,
                    prompt_student=question.prompt_student,
                    prompt_formal=question.prompt_formal,
                    max_length=question.max_length,
                )
                for question in INTAKE_QUESTIONS
            ],
            crisis_support_resources=self._crisis_resources(),
        )

    async def create_appeal(self, payload: AppealCreateRequest) -> CreatedAppealResult:
        description = (
            payload.description.get_secret_value().strip() if payload.description else ""
        )
        intake_answers = {
            question_id: answer.get_secret_value().strip()
            for question_id, answer in (payload.intake_answers or {}).items()
            if answer.get_secret_value().strip()
        }
        category = None
        if payload.category_id is not None:
            category = await self._repository.get_category(payload.category_id)
            if category is None or not category.is_active:
                raise ValidationError("Choose an available category.")
            if category.slug == UNKNOWN_CATEGORY_SLUG and not description:
                raise ValidationError("Please describe the situation in your own words.")
        if category is None and not description:
            raise ValidationError("Choose a category or describe the situation.")

        patterns = (
            await self._crisis_rules.active_patterns() if self._crisis_rules is not None else None
        )
        detector = CrisisDetector(patterns) if patterns is not None else CrisisDetector()
        crisis_flag = detector.detect([description, *intake_answers.values()])
        for _attempt in range(5):
            track_number = generate_track_number()
            track_digest = track_lookup_digest(self._track_secret, track_number)
            if await self._repository.track_digest_exists(track_digest):
                continue
            appeal_id = uuid4()
            appeal = Appeal(
                id=appeal_id,
                track_digest=track_digest,
                applicant_type=payload.applicant_type,
                category_id=category.id if category else None,
                status=AppealStatus.NEW,
                priority=AppealPriority.STANDARD,
                crisis_flag=crisis_flag,
                return_count=0,
            )
            content = (
                AppealContent(
                    appeal_id=appeal_id,
                    encrypted_content=self._crypto.encrypt_text(
                        description, aad=appeal_content_aad(appeal_id)
                    ),
                    key_version=self._crypto.key_version,
                )
                if description
                else None
            )
            answers = (
                AppealIntakeAnswer(
                    appeal_id=appeal_id,
                    encrypted_payload=self._crypto.encrypt_json(
                        intake_answers, aad=intake_answers_aad(appeal_id)
                    ),
                    key_version=self._crypto.key_version,
                )
                if intake_answers
                else None
            )
            initial_history = StatusHistory(
                id=uuid4(),
                appeal_id=appeal_id,
                from_status=None,
                to_status=AppealStatus.NEW,
                changed_by_staff_user_id=None,
            )
            try:
                await self._repository.add_appeal_bundle(
                    appeal, content, answers, initial_history
                )
                await self._repository.commit()
            except IntegrityError:
                await self._repository.rollback()
                continue
            response = AppealCreatedResponse(
                track_number=track_number,
                status=AppealStatus.NEW,
                status_text=applicant_status_text(AppealStatus.NEW, payload.applicant_type),
                crisis_flag=crisis_flag,
                show_crisis_support=crisis_flag,
                crisis_support_resources=self._crisis_resources(),
            )
            return CreatedAppealResult(
                response=response,
                access_token=self._access_tokens.issue(appeal_id),
            )
        raise InfrastructureError("A unique appeal track number could not be allocated.")

    async def access_appeal(self, supplied_track_number: str) -> AppealAccessResult:
        valid_format = True
        try:
            normalized = normalize_track_number(supplied_track_number)
        except ValueError:
            normalized = _INVALID_TRACK_PLACEHOLDER
            valid_format = False
        digest = track_lookup_digest(self._track_secret, normalized)
        appeal = await self._repository.get_appeal_by_digest(digest)
        if not valid_format or appeal is None:
            raise UnauthorizedError(INVALID_TRACK_MESSAGE)
        return AppealAccessResult(
            appeal_id=appeal.id,
            access_token=self._access_tokens.issue(appeal.id),
        )

    def decode_access_token(self, token: str) -> UUID:
        return self._access_tokens.decode(token).appeal_id

    async def current_appeal(self, appeal_id: UUID) -> CurrentAppealResponse:
        record = await self._repository.get_appeal_with_category(appeal_id)
        if record is None:
            raise UnauthorizedError("Appeal access is invalid or expired.")
        appeal = record.appeal
        history = await self._repository.list_status_history(appeal_id)
        rejection = (
            await self._repository.get_rejection(appeal_id)
            if appeal.status is AppealStatus.REJECTED
            else None
        )
        return CurrentAppealResponse(
            applicant_type=appeal.applicant_type,
            category=self._category_public(record.category) if record.category else None,
            status=appeal.status,
            status_text=applicant_status_text(appeal.status, appeal.applicant_type),
            crisis_flag=appeal.crisis_flag,
            show_crisis_support=appeal.crisis_flag,
            crisis_support_resources=self._crisis_resources(),
            created_at=appeal.created_at,
            updated_at=appeal.updated_at,
            timeline=[
                StatusTimelineItem(
                    status=item.to_status,
                    text=applicant_status_text(item.to_status, appeal.applicant_type),
                    occurred_at=item.created_at,
                )
                for item in history
            ],
            rejection_reason=(
                self._crypto.decrypt_text(
                    rejection.encrypted_reason, aad=rejection_reason_aad(appeal_id)
                )
                if rejection
                else None
            ),
        )

    async def save_crisis_contact(self, appeal_id: UUID, contact: str) -> None:
        appeal = await self._repository.get_appeal(appeal_id)
        if appeal is None:
            raise UnauthorizedError("Appeal access is invalid or expired.")
        if not appeal.crisis_flag:
            raise ForbiddenError("A crisis contact is only available for a crisis appeal.")
        normalized_contact = contact.strip()
        if not normalized_contact:
            raise ValidationError("Contact information cannot be blank.")
        await self._repository.upsert_crisis_contact(
            CrisisContact(
                appeal_id=appeal_id,
                encrypted_contact=self._crypto.encrypt_text(
                    normalized_contact, aad=crisis_contact_aad(appeal_id)
                ),
                key_version=self._crypto.key_version,
            )
        )
        await self._repository.commit()

    def _crisis_resources(self) -> list[CrisisSupportResourcePublic]:
        return [
            CrisisSupportResourcePublic(
                title=self._settings.crisis_support_title,
                message=self._settings.crisis_support_message,
                phone=self._settings.crisis_support_phone or None,
                url=self._settings.crisis_support_url or None,
                requires_organizer_verification=(
                    self._settings.crisis_support_requires_organizer_verification
                ),
            )
        ]

    @staticmethod
    def _category_public(category: Category) -> CategoryPublic:
        return CategoryPublic(
            id=category.id,
            slug=category.slug,
            name=category.name,
            description=category.description,
            requires_description=category.slug == UNKNOWN_CATEGORY_SLUG,
        )
