import subprocess
from pathlib import Path
from uuid import UUID, uuid4

API_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = API_ROOT.parents[1]
PHASE_2A_REVISION = "20260909_0002"


def _psql(sql: str) -> subprocess.CompletedProcess[str]:
    """Run psql inside the Compose PostgreSQL service without exposing credentials."""

    return subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "sh",
            "-c",
            'psql -X -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
        ],
        cwd=REPOSITORY_ROOT,
        input=sql,
        capture_output=True,
        text=True,
        check=False,
    )


def _appeal_insert(appeal_id: UUID, digest_byte: str = "74") -> str:
    return (
        "INSERT INTO appeals (id, track_digest, applicant_type) VALUES "
        f"('{appeal_id}', decode(repeat('{digest_byte}', 32), 'hex'), 'student');"
    )


def _staff_insert(staff_id: UUID) -> str:
    return (
        "INSERT INTO staff_users (id, login, password_hash, role, display_name) VALUES "
        f"('{staff_id}', 'expert-{staff_id}', 'unused-phase-2a-hash', "
        "'expert', 'Integration Expert');"
    )


def test_alembic_upgrade_reaches_phase_2a_revision() -> None:
    result = _psql("SELECT version_num FROM alembic_version;")

    assert result.returncode == 0, result.stderr
    assert PHASE_2A_REVISION in result.stdout


def test_unique_track_digest_is_enforced() -> None:
    first_appeal_id = uuid4()
    second_appeal_id = uuid4()
    sql = "\n".join(
        [
            "BEGIN;",
            _appeal_insert(first_appeal_id),
            _appeal_insert(second_appeal_id),
        ]
    )

    result = _psql(sql)

    assert result.returncode != 0
    assert "ix_appeals_track_digest" in result.stderr


def test_track_digest_must_be_sha256_length() -> None:
    sql = (
        "BEGIN;\n"
        "INSERT INTO appeals (id, track_digest, applicant_type) VALUES "
        f"('{uuid4()}', decode('74', 'hex'), 'teacher');"
    )

    result = _psql(sql)

    assert result.returncode != 0
    assert "appeals_track_digest_length" in result.stderr


def test_rating_and_message_author_checks_are_enforced() -> None:
    appeal_id = uuid4()
    staff_id = uuid4()
    invalid_rating = "\n".join(
        [
            "BEGIN;",
            _appeal_insert(appeal_id, "75"),
            "INSERT INTO appeal_feedback (id, appeal_id, rating) "
            f"VALUES ('{uuid4()}', '{appeal_id}', 6);",
        ]
    )
    invalid_message_author = "\n".join(
        [
            "BEGIN;",
            _staff_insert(staff_id),
            _appeal_insert(appeal_id, "76"),
            "INSERT INTO appeal_messages "
            "(id, appeal_id, author_type, author_staff_user_id, encrypted_body, key_version) "
            f"VALUES ('{uuid4()}', '{appeal_id}', 'applicant', '{staff_id}', "
            "decode('00', 'hex'), 1);",
        ]
    )

    rating_result = _psql(invalid_rating)
    author_result = _psql(invalid_message_author)

    assert rating_result.returncode != 0
    assert "appeal_feedback_rating_range" in rating_result.stderr
    assert author_result.returncode != 0
    assert "appeal_messages_author_consistency" in author_result.stderr


def test_only_one_active_primary_participant_is_enforced() -> None:
    appeal_id = uuid4()
    first_staff_id = uuid4()
    second_staff_id = uuid4()
    sql = "\n".join(
        [
            "BEGIN;",
            _staff_insert(first_staff_id),
            _staff_insert(second_staff_id),
            _appeal_insert(appeal_id, "77"),
            "INSERT INTO appeal_participants "
            "(id, appeal_id, staff_user_id, participant_role) "
            f"VALUES ('{uuid4()}', '{appeal_id}', '{first_staff_id}', 'primary');",
            "INSERT INTO appeal_participants "
            "(id, appeal_id, staff_user_id, participant_role) "
            f"VALUES ('{uuid4()}', '{appeal_id}', '{second_staff_id}', 'primary');",
        ]
    )

    result = _psql(sql)

    assert result.returncode != 0
    assert "uq_appeal_participants_current_primary" in result.stderr
