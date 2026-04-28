# Test Factories

## Conventions
- Keep factories split by domain (`world.py`, `player.py`, `jobs.py`, etc.).
- Put reusable defaults in factories; put business-state variants in `Trait`s.
- Use `create()` only when the test needs persistence; otherwise prefer `build()`.
- Keep `post_generation` hooks minimal and explicit (M2M attachment only).
- Avoid hard-coded primary keys in tests; rely on relations and explicit keys when needed.
- Do not recreate giant fixture-style object graphs in a single factory.

## Migration guidance
- Existing helper functions in `game/tests/test_factories.py` are compatibility wrappers.
- New tests should import from `game.tests.factories` directly.
