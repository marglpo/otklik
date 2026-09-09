from app.core.errors import ConflictError
from app.db.models.enums import AppealStatus

_OPERATOR_TRANSITIONS = {
    AppealStatus.NEW: {AppealStatus.ASSIGNED, AppealStatus.REJECTED},
    AppealStatus.RETURNED: {AppealStatus.ASSIGNED, AppealStatus.REJECTED},
}


def require_operator_transition(current: AppealStatus, target: AppealStatus) -> None:
    if target not in _OPERATOR_TRANSITIONS.get(current, set()):
        raise ConflictError(f"Appeal cannot transition from {current.value} to {target.value}.")


def require_triage_status(current: AppealStatus) -> None:
    if current not in _OPERATOR_TRANSITIONS:
        raise ConflictError("Only new or returned appeals can be triaged by an operator.")
