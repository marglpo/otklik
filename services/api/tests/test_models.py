import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models.enums import (
    AppealParticipantRole,
    AppealPriority,
    AppealStatus,
    ApplicantType,
    MessageAuthorType,
    StaffRole,
    TransferRequestStatus,
)


def test_phase_2a_defines_expected_tables() -> None:
    assert set(Base.metadata.tables) == {
        "appeal_contents",
        "appeal_feedback",
        "appeal_intake_answers",
        "appeal_messages",
        "appeal_participants",
        "appeals",
        "assignment_history",
        "attachments",
        "audit_log",
        "categories",
        "category_group_rules",
        "crisis_contacts",
        "expert_group_memberships",
        "expert_profiles",
        "internal_notes",
        "specialist_groups",
        "staff_complaints",
        "staff_users",
        "status_history",
        "transfer_requests",
    }


def test_domain_enums_use_stable_lowercase_values() -> None:
    enum_classes = (
        ApplicantType,
        StaffRole,
        AppealStatus,
        AppealPriority,
        AppealParticipantRole,
        TransferRequestStatus,
        MessageAuthorType,
    )

    for enum_class in enum_classes:
        assert all(member.value == member.value.lower() for member in enum_class)


def test_models_do_not_expose_applicant_identity_fields() -> None:
    forbidden_columns = {
        "advertising_id",
        "analytics_identifier",
        "applicant_email",
        "applicant_id",
        "applicant_name",
        "applicant_phone",
        "browser_fingerprint",
        "device_fingerprint",
        "email",
        "ip_address",
        "phone",
        "school",
        "user_agent",
    }

    all_columns = {
        column.name for table in Base.metadata.tables.values() for column in table.columns
    }
    assert forbidden_columns.isdisjoint(all_columns)


def test_appeals_has_only_a_digest_for_track_lookup() -> None:
    appeal_columns = set(Base.metadata.tables["appeals"].columns.keys())

    assert "track_digest" in appeal_columns
    assert {"track_number", "track_code", "plaintext_track"}.isdisjoint(appeal_columns)


def test_crisis_contact_is_separate_from_appeal_metadata() -> None:
    appeal_columns = set(Base.metadata.tables["appeals"].columns.keys())

    assert "encrypted_contact" not in appeal_columns
    assert "encrypted_contact" in Base.metadata.tables["crisis_contacts"].columns


def test_appeal_content_is_separate_from_metadata() -> None:
    appeal_columns = set(Base.metadata.tables["appeals"].columns.keys())

    assert "encrypted_content" not in appeal_columns
    assert "encrypted_content" in Base.metadata.tables["appeal_contents"].columns


def test_attachments_do_not_store_identifying_filenames_or_public_urls() -> None:
    attachment_columns = set(Base.metadata.tables["attachments"].columns.keys())

    assert {"original_filename", "filename", "public_url"}.isdisjoint(attachment_columns)
