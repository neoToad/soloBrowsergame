**Top Findings (Prioritized)**

1. **Service-layer boundary is violated in gameplay views (high risk).**  
Business logic is still in views: routing, requirements evaluation, flags mutation, arrival effects, combat setup, and response orchestration are mixed in HTTP handlers.  
Files: [views.py:99](C:\Users\colin\PycharmProjects\soloBrowserGame\game\views.py:99), [views.py:157](C:\Users\colin\PycharmProjects\soloBrowserGame\game\views.py:157), [views.py:341](C:\Users\colin\PycharmProjects\soloBrowserGame\game\views.py:341)

2. **Quest/scene domain model is over-coupled and ambiguous (high risk).**  
`Quest.scenes` is M2M while `Scene.key` is globally unique, and quest completion uses `next_scene.quests.first()`, which can be nondeterministic if scenes are reused across quests.  
Files: [world.py:56](C:\Users\colin\PycharmProjects\soloBrowserGame\game\models\world.py:56), [world.py:76](C:\Users\colin\PycharmProjects\soloBrowserGame\game\models\world.py:76), [progression.py:103](C:\Users\colin\PycharmProjects\soloBrowserGame\game\services\progression.py:103)

3. **Import pipeline has dangerous duplication and shared-state bugs (high risk).**  
`import_all.py` and `import_quest.py` duplicate substantial logic. Both reuse `RequirementGroup` by label and then clear/rebuild requirements, which can accidentally mutate unrelated content sharing the same label.  
Files: [import_all.py:326](C:\Users\colin\PycharmProjects\soloBrowserGame\game\management\commands\import_all.py:326), [import_quest.py:162](C:\Users\colin\PycharmProjects\soloBrowserGame\game\management\commands\import_quest.py:162)

4. **Large “god modules” are reducing maintainability and testability (high risk).**  
Very large files with mixed concerns:  
- [quest_builder.py](C:\Users\colin\PycharmProjects\soloBrowserGame\game\services\quest_builder.py) (canvas graph, validation, form parsing, CRUD, requirement parsing)  
- [jobs.py](C:\Users\colin\PycharmProjects\soloBrowserGame\game\services\jobs.py) (listing, lifecycle, rewards, cooldowns, flag state, rolls)  
- [admin.py](C:\Users\colin\PycharmProjects\soloBrowserGame\game\admin.py) (admin config + quest-builder routing)

5. **State management relies on mutable JSON flags and implicit conventions (medium-high risk).**  
Flags are ad-hoc strings (`approach_*`, penalty flag), mutated from multiple places; no typed contract or namespace policy.  
Files: [flags.py:5](C:\Users\colin\PycharmProjects\soloBrowserGame\game\services\flags.py:5), [jobs.py:375](C:\Users\colin\PycharmProjects\soloBrowserGame\game\services\jobs.py:375), [jobs.py:546](C:\Users\colin\PycharmProjects\soloBrowserGame\game\services\jobs.py:546)

6. **Randomness + DB side effects are tightly coupled (medium risk).**  
Combat/jobs/property flows combine random rolls and persistence in same functions, making deterministic tests hard.  
Files: [combat.py:78](C:\Users\colin\PycharmProjects\soloBrowserGame\game\services\combat.py:78), [jobs.py:476](C:\Users\colin\PycharmProjects\soloBrowserGame\game\services\jobs.py:476), [property_service.py:43](C:\Users\colin\PycharmProjects\soloBrowserGame\game\services\property_service.py:43)

7. **Inconsistent API/view response patterns (medium risk).**  
Some endpoints return full HTML, some empty + HX triggers, some redirects, some plain text errors; hard to reason about contracts.  
Files: [views.py:145](C:\Users\colin\PycharmProjects\soloBrowserGame\game\views.py:145), [quest_builder_views.py:468](C:\Users\colin\PycharmProjects\soloBrowserGame\game\quest_builder_views.py:468), [quest_builder_views.py:493](C:\Users\colin\PycharmProjects\soloBrowserGame\game\quest_builder_views.py:493)

8. **Naming/clarity issues and encoding artifacts (medium risk).**  
`intellect` vs “cunning” terminology drifts; some strings/comments contain mojibake (for example broken dash/arrow sequences) which hurts readability and can leak to UI/admin.  
Files: [jobs.py:111](C:\Users\colin\PycharmProjects\soloBrowserGame\game\services\jobs.py:111), [scene.py:29](C:\Users\colin\PycharmProjects\soloBrowserGame\game\services\scene.py:29), [world.py:221](C:\Users\colin\PycharmProjects\soloBrowserGame\game\models\world.py:221)

9. **Test organization is inconsistent and coverage is weak in critical services (medium risk).**  
Mixed test style (`tests.py` monolith + split modules). Coverage report shows low coverage in critical logic (`quest_builder_views`, `combat`, `arrival`, `inventory`, `progression`).  
Files: [tests.py](C:\Users\colin\PycharmProjects\soloBrowserGame\game\tests\tests.py), [quest_builder_views.py](C:\Users\colin\PycharmProjects\soloBrowserGame\game\quest_builder_views.py), [combat.py](C:\Users\colin\PycharmProjects\soloBrowserGame\game\services\combat.py)

---

**Architectural Issues**

1. **Folder structure / module ownership**
- Admin quest-builder endpoints live in `admin.py` route extension + separate `quest_builder_views.py` + `services/quest_builder.py`; ownership is fragmented.
- Import logic is command-centric instead of shared import service layer.

2. **Pattern violations**
- MVC/service-layer intent is violated in `game/views.py` (domain orchestration in views).
- Import commands bypass service abstractions and directly manipulate many models.

3. **State management**
- Session flags are effectively global mutable state for job flow.
- Combat pending attack is JSON payload in DB (`pending_enemy_attack`) rather than typed state transitions.

4. **API design consistency**
- Similar interaction endpoints return materially different response types/shape.
- Error responses are plain strings with inconsistent status/messages.

---

**Highest-Risk Files to Refactor First**

1. [game/views.py](C:\Users\colin\PycharmProjects\soloBrowserGame\game\views.py)  
2. [game/services/jobs.py](C:\Users\colin\PycharmProjects\soloBrowserGame\game\services\jobs.py)  
3. [game/services/quest_builder.py](C:\Users\colin\PycharmProjects\soloBrowserGame\game\services\quest_builder.py)  
4. [game/management/commands/import_all.py](C:\Users\colin\PycharmProjects\soloBrowserGame\game\management\commands\import_all.py) and [import_quest.py](C:\Users\colin\PycharmProjects\soloBrowserGame\game\management\commands\import_quest.py)  
5. [game/services/combat.py](C:\Users\colin\PycharmProjects\soloBrowserGame\game\services\combat.py)

---

**Prioritized Refactor Plan**


2. **Enforce application-service boundary.**  DONE
Introduce `game/services/gameplay/` use-case services (`resolve_choice`, `start_quest`, `run_combat_turn`, `use_item`) and reduce views to request parsing + response mapping.

3. **Fix quest/scene ownership model.** DONE 
Decide ownership model explicitly:
- Preferred: `Scene` belongs to exactly one `Quest` (FK), 

4. **Consolidate import system.**   DONE
Create shared import services (`services/importers/*`) and make management commands thin wrappers.  
Replace label-based requirement-group reuse with explicit scoped identifiers.

5. **Split `jobs.py` by concern.**  DONE
Separate modules for: eligibility/listing, lifecycle transitions, rewards/cooldowns, roll engine, flag policy.

6. **Make state transitions explicit and typed.** DONE  
Wrap flags in a typed API (enum/constants + helper methods).  
Move combat pending attack from raw dict to explicit fields or a dedicated transition object.

7. **Standardize endpoint contracts.**  Done
Define consistent HTMX response strategy (partial HTML + trigger schema + structured errors).

8. **Clean naming and encoding.** DONE  
Normalize “intellect/cunning” naming policy and remove mojibake artifacts across user/admin text.

9. **Test suite cleanup.**  
Split `game/tests/tests.py` into domain-focused modules; keep one test style and shared factories only.
