from app.db.models.enums import AppealStatus, ApplicantType

_STATUS_TEXT: dict[AppealStatus, tuple[str, str]] = {
    AppealStatus.NEW: (
        "Мы получили твоё обращение. Скоро его внимательно посмотрит специалист.",
        "Мы получили ваше обращение. Скоро его внимательно посмотрит специалист.",
    ),
    AppealStatus.ASSIGNED: (
        "Обращение передано подходящему специалисту.",
        "Обращение передано подходящему специалисту.",
    ),
    AppealStatus.IN_PROGRESS: (
        "Специалист работает с твоим обращением.",
        "Специалист работает с вашим обращением.",
    ),
    AppealStatus.NEEDS_CLARIFICATION: (
        "Специалисту понадобится уточнение. Возможность ответить появится позже.",
        "Специалисту понадобится уточнение. Возможность ответить появится позже.",
    ),
    AppealStatus.ANSWER_READY: (
        "Для тебя подготовлен ответ.",
        "Для вас подготовлен ответ.",
    ),
    AppealStatus.RETURNED: (
        "Обращение уточняют, чтобы подобрать подходящую помощь.",
        "Обращение уточняют, чтобы подобрать подходящую помощь.",
    ),
    AppealStatus.COMPLETED: (
        "Работа с обращением завершена.",
        "Работа с обращением завершена.",
    ),
    AppealStatus.REJECTED: (
        "Сейчас обращение не может быть принято в работу.",
        "Сейчас обращение не может быть принято в работу.",
    ),
    AppealStatus.CLOSED_NO_RESPONSE: (
        "Обращение закрыто после ожидания ответа.",
        "Обращение закрыто после ожидания ответа.",
    ),
}


def applicant_status_text(status: AppealStatus, applicant_type: ApplicantType) -> str:
    student_text, formal_text = _STATUS_TEXT[status]
    return student_text if applicant_type is ApplicantType.STUDENT else formal_text
