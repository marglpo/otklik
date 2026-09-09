"""Central policy boundary for future appeal authorization.

Role membership alone must never grant access to sensitive appeal data. Future
appeal queries must additionally enforce workflow state and assignment or
participation. Operators may see intake content during triage and manage routing;
experts may see chat and internal notes only for assigned/participating appeals.
Administrators manage staff, taxonomy, routing metadata, analytics, and audit, but
must not receive appeal text, chat, or crisis contacts merely because they are admins.
"""

from app.db.models.enums import StaffRole


class AccessPolicy:
    @staticmethod
    def operator_may_triage(role: StaffRole) -> bool:
        return role is StaffRole.OPERATOR

    @staticmethod
    def operator_may_read_triage_content(role: StaffRole) -> bool:
        return role is StaffRole.OPERATOR

    @staticmethod
    def operator_may_read_crisis_contact(role: StaffRole) -> bool:
        return role is StaffRole.OPERATOR

    @staticmethod
    def can_manage_staff(role: StaffRole) -> bool:
        return role is StaffRole.ADMIN

    @staticmethod
    def can_manage_routing_metadata(role: StaffRole) -> bool:
        return role in {StaffRole.OPERATOR, StaffRole.ADMIN}

    @staticmethod
    def role_alone_grants_sensitive_appeal_access(_role: StaffRole) -> bool:
        """Sensitive content always requires future appeal-context checks."""

        return False

    @staticmethod
    def admin_may_read_appeal_content() -> bool:
        return False

    @staticmethod
    def admin_may_read_crisis_contact() -> bool:
        return False
