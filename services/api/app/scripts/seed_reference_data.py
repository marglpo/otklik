import asyncio
from uuid import uuid4

from app.core.config import get_settings
from app.db import create_database
from app.db.models import Category, CrisisRule
from app.db.repositories.crisis_rules import CrisisRuleRepository
from app.db.repositories.public_appeals import PublicAppealRepository
from app.modules.categories.reference_data import STARTER_CATEGORIES, CategoryDefinition
from app.modules.crisis.detector import DEFAULT_CRISIS_RULES


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


async def seed_crisis_rules(repository: CrisisRuleRepository) -> tuple[int, int]:
    created = 0
    updated = 0
    for sort_order, definition in enumerate(DEFAULT_CRISIS_RULES, start=1):
        rule = await repository.get_by_normalized_phrase(definition.normalized_phrase)
        if rule is None:
            await repository.add(
                CrisisRule(
                    id=uuid4(),
                    phrase=definition.normalized_phrase,
                    normalized_phrase=definition.normalized_phrase,
                    compact_phrase=definition.compact_phrase,
                    is_active=True,
                    allow_compact_match=definition.allow_compact_match,
                    sort_order=sort_order * 10,
                )
            )
            created += 1
            continue
        # Existing rows are administrator-managed metadata. Re-running the seed must not
        # reactivate or overwrite a rule that an administrator changed intentionally.
    await repository.commit()
    return created, updated


async def seed_reference_data() -> None:
    settings = get_settings()
    database = create_database(settings.database_url)
    try:
        async with database.session_factory() as session:
            categories = await seed_categories(PublicAppealRepository(session))
            crisis_rules = await seed_crisis_rules(CrisisRuleRepository(session))
    finally:
        await database.close()
    print(
        "Reference seed complete: "
        f"categories={categories[0]} created/{categories[1]} updated; "
        f"crisis_rules={crisis_rules[0]} created/{crisis_rules[1]} updated."
    )


def main() -> None:
    asyncio.run(seed_reference_data())


if __name__ == "__main__":
    main()
