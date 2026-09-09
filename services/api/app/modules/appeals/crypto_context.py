from uuid import UUID


def appeal_content_aad(appeal_id: UUID) -> bytes:
    return b"otklik:appeal-content:" + appeal_id.bytes


def intake_answers_aad(appeal_id: UUID) -> bytes:
    return b"otklik:intake-answers:" + appeal_id.bytes


def crisis_contact_aad(appeal_id: UUID) -> bytes:
    return b"otklik:crisis-contact:" + appeal_id.bytes


def attachment_aad(appeal_id: UUID, attachment_id: UUID) -> bytes:
    return b"otklik:attachment:" + appeal_id.bytes + attachment_id.bytes
