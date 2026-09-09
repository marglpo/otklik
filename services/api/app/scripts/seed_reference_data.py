import asyncio
from uuid import uuid4

from app.core.config import get_settings
from app.db import create_database
from app.db.models import Category
from app.db.repositories.public_appeals import PublicAppealRepository
from app.modules.categories.reference_data import STARTER_CATEGORIES, CategoryDefinition


async def seed_categories(
    repository: PublicAppealRepository,
    definitions: tuple[CategoryDefinition, ...] = STARTER_CATEGORIES,
) -> tuple[int, int]:
    created = 0
    updated = 0
    for definition in definitions:
        category = await repository.get_category_by_slug(definition.slug)
        if category is None:
            await repository.add_category(
                Category(
                    id=uuid4(),
                    slug=definition.slug,
                    name=definition.name,
                    description=definition.description,
                    sort_order=definition.sort_order,
                    is_active=True,
                )
            )
            created += 1
            continue
        changed = (
            category.name != definition.name
            or category.description != definition.description
            or category.sort_order != definition.sort_order
            or not category.is_active
        )
        category.name = definition.name
        category.description = definition.description
        category.sort_order = definition.sort_order
        category.is_active = True
        updated += int(changed)
    await repository.commit()
    return created, updated


async def seed_reference_data() -> None:
    settings = get_settings()
    database = create_database(settings.database_url)
    try:
        async with database.session_factory() as session:
            created, updated = await seed_categories(PublicAppealRepository(session))
    finally:
        await database.close()
    print(f"Reference seed complete: {created} created, {updated} updated.")


def main() -> None:
    asyncio.run(seed_reference_data())


if __name__ == "__main__":
    main()
