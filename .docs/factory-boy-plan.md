# Factory-Boy Adoption Plan

1. Audit current tests and models.
- List the most-used models in failing/slow/verbose tests first.
- Identify repeated setup patterns to replace first.

2. Create a factory structure.
- Add a `tests/factories/` package (split by domain, not one giant file).
- Add a shared `BaseFactory` with common defaults (`django_get_or_create` only when truly needed).

3. Implement core factories first.
- Start with foundational models (for example: `User`, profile, world/game/session roots).
- Use `SubFactory` for required relations and `RelatedFactory` only when behavior requires it.

4. Add traits for common scenarios.
- Encode business states as traits (for example: `active`, `completed`, `with_rewards`) instead of copy-paste setup.
- Keep trait names aligned with service-layer language.

5. Handle M2M and post-generation cleanly.
- Use `post_generation` hooks for tags/permissions/inventory lists.
- Keep hooks minimal; avoid hidden side effects.

6. Convert tests incrementally.
- Replace repeated setup in high-churn test modules first.
- Keep fixtures only for static reference data; use factories for mutable test entities.

7. Improve reliability and speed.
- Seed Faker in test settings for deterministic runs.
- Use `build()` where DB rows are unnecessary; `create()` only when persistence matters.

8. Add guardrails.
- Add a short `tests/factories/README.md` with conventions.
- Add lint/check guidance for avoiding hard-coded IDs and giant fixtures.

9. Validate and clean up.
- Run targeted test modules after each conversion batch.
- Remove obsolete fixtures and dead helper builders once coverage is migrated.
