# Refactor Implementation Prompt Pack

Use these prompts one at a time in a coding agent. Each prompt assumes this repo�s architecture rule: business logic must live in services, not views.

## 15) Add route-shape validation boundary for scene/choice routing semantics

```text
Introduce a single validation boundary for scene/choice route semantics currently spread across models/services/views.

Requirements:
1. Add validator(s) in model/service layer (not views), likely under:
   - `game/models/world.py` for model invariants
   - `game/services/quest_builder/validation.py` for workflow-level checks
2. Cover target/success/failure routing compatibility with scene types and quest ownership constraints.
3. Ensure errors are actionable and consistent for admin quest builder.
4. Add tests for invalid/valid routing combinations.

Deliverables:
- Centralized routing validation with reduced duplicated assumptions.
```

## 16) Optional sequencing meta-prompt (run this before prompt 1)

```text
Create an execution plan for the refactor prompts in `.docs/refactor-implementation-prompts.md` with dependency ordering, expected risk, and test strategy per step.

Output format:
- Ordered checklist with: `step`, `depends_on`, `risk`, `tests_to_run`, `rollback_plan`.
- Keep each step small enough for a single PR.
```
