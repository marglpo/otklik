import argparse
import asyncio
from dataclasses import dataclass

from pydantic import SecretStr

from app.core.config import AppEnvironment, Settings, get_settings
from app.db import create_database
from app.db.models import ExpertProfile
from app.db.models.enums import StaffRole
from app.db.repositories.staff_auth import StaffAuthRepository
from app.modules.auth.service import normalize_login
from app.modules.staff.service import StaffManagementService


@dataclass(frozen=True, slots=True)
class DemoStaffDefinition:
    login: str
    password: SecretStr | None
    display_name: str
    role: StaffRole


def _definitions(settings: Settings) -> tuple[DemoStaffDefinition, ...]:
    return (
        DemoStaffDefinition(
            settings.demo_operator_login,
            settings.demo_operator_password,
            "Demo Operator",
            StaffRole.OPERATOR,
        ),
        DemoStaffDefinition(
            settings.demo_expert_login,
            settings.demo_expert_password,
            "Demo Expert",
            StaffRole.EXPERT,
        ),
        DemoStaffDefinition(
            settings.demo_admin_login,
            settings.demo_admin_password,
            "Demo Administrator",
            StaffRole.ADMIN,
        ),
    )


async def seed_demo_staff(settings: Settings, *, allow_production: bool = False) -> None:
    if settings.app_env is AppEnvironment.PRODUCTION and not allow_production:
        raise RuntimeError("Demo staff seeding is disabled in production.")
    definitions = _definitions(settings)
    if any(item.password is None or not item.password.get_secret_value() for item in definitions):
        raise RuntimeError("All DEMO_*_PASSWORD environment variables must be configured.")

    database = create_database(settings.database_url)
    created = 0
    try:
        async with database.session_factory() as session:
            repository = StaffAuthRepository(session)
            created = await _seed_definitions(repository, definitions)
    finally:
        await database.close()
    print(f"Demo staff seed complete: {created} created, {len(definitions) - created} existing.")


async def _seed_definitions(
    repository: StaffAuthRepository,
    definitions: tuple[DemoStaffDefinition, ...],
) -> int:
    service = StaffManagementService(repository)
    created = 0
    for definition in definitions:
        login = normalize_login(definition.login)
        existing = await repository.get_staff_by_login(login)
        if existing is not None:
            if existing.role is not definition.role:
                raise RuntimeError(f"Existing demo login has a different role: {login}")
            if definition.role is StaffRole.EXPERT:
                profile = await repository.get_expert_profile(existing.id)
                if profile is None:
                    await repository.add_expert_profile(
                        ExpertProfile(staff_user_id=existing.id)
                    )
                    await repository.commit()
            continue
        password = definition.password
        if password is None or not password.get_secret_value():
            raise RuntimeError("Demo staff passwords must be configured.")
        await service.create_staff_user(
            login=login,
            password=password.get_secret_value(),
            role=definition.role,
            display_name=definition.display_name,
        )
        created += 1
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Create idempotent development demo staff.")
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Explicitly allow demo seeding when APP_ENV=production.",
    )
    args = parser.parse_args()
    asyncio.run(seed_demo_staff(get_settings(), allow_production=args.allow_production))


if __name__ == "__main__":
    main()
