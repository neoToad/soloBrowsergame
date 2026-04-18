
## Phase 2 — Security

### 5. Add ownership check in `choice_resolve`
**File:** `game/views.py:107`  
**Severity:** Medium (security)  
**Problem:** `choice_resolve` fetches any `Choice` by PK from the URL with no check that it belongs to `session.current_scene`. A player can POST to `/game/choose/<any_id>/` and execute choices they've never seen, bypassing requirement gates.  
**Fix:** After fetching the choice, assert `choice.scene == session.current_scene` (or `choice.scene_id == session.current_scene_id`). Return 403 or redirect to current scene on failure.

---

### 6. Externalize `SECRET_KEY`
**File:** `core/settings.py:23`  
**Severity:** Medium (security)  
**Problem:** Hardcoded `SECRET_KEY = 'django-insecure-...'`.  
**Fix:**
```python
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
```
Document in `.env.example`. Not urgent for local dev, but required before any deployment.

---

## Phase 3 — Architecture (Dependency Order Matters)

### 7. Move `build_render_context` to `views.py`
**File:** `game/services/session.py` → `game/views.py`  
**Severity:** Medium  
**Problem:** This function assembles a template context dict — HTTP-layer work — placed in the service layer. It causes the circular import that forces inline imports across multiple view functions.  
**Fix:** Move to `views.py` as `_build_render_context(...)`. Update all callers. This unblocks tasks 8 and 9.  
**Depends on:** Nothing — do this first in phase 3.

---

### 8. Strip `EventLog` writes from `combat.py` services
**File:** `game/services/combat.py:86-88,108-118`  
**Severity:** Medium  
**Problem:** `get_or_create_combat_state` and `resolve_combat_end` write `EventLog.objects.create()` directly, breaking the documented contract that services return log strings and views write them. Makes the service untestable without a full DB + request cycle.  
**Fix:** Return log strings from the service functions. Let the calling view write `EventLog` entries.  
**Depends on:** Task 7 (moving `build_render_context` out of `resolve_combat_end`'s reach).

---

### 9. Extract `choice_resolve` body into a service
**File:** `game/views.py:98-196`  
**Severity:** Medium  
**Problem:** 98 lines of business logic live directly in the view, including an inline `RivalClaim` query at line 163 that should be `property_service.resolve_contest_if_applicable(session, next_scene)`.  
**Fix:** Extract to `game/services/session.py` (or a new `game/services/choice.py`) as `resolve_choice_transition(session, choice, stats, inventory, completed_map) -> (next_scene, log_entries, turn_summary)`. Move the `RivalClaim` logic into `property_service`.  
**Depends on:** Tasks 7 and 8.

---

## Phase 4 — Performance

### 10. Fix N+1 in `get_available_choices` and `get_notice_board`
**File:** `game/services/scene.py:35-38,108-117`  
**Severity:** Medium  
**Problem:** Every call fires one query per choice × one query per requirement group × one query per requirement. A scene with 5 choices, 2 groups each, 3 requirements each = 25 queries.  
**Fix:**
```python
scene.choices.prefetch_related('requirements__requirements').select_related('quest')
```
In `get_notice_board`, replace `quest.requirements.exists()` with `if quest.requirements.all():` to use the prefetch cache instead of firing a new query.  
**Optional:** Extract as a queryset helper `prefetch_choices_with_requirements(qs)` for reuse in `scene_detail`.

---

### 11. Fix queryset double-evaluation in `property_service.py`
**File:** `game/services/property_service.py:37,62,67`  
**Severity:** Low  
**Fixes:**
- `process_turn_income`: replace `if properties.exists():` with `if logs:` (list already built by the loop).
- `check_rival_contests`: materialize `contestable_list = list(contestable)` once; replace `.exists()` check with `if not contestable_list:`.

---

## Phase 5 — Model / Data Quality

### 12. Add `choices=` to `Scene.roll_stat`
**File:** `game/models/world.py`  
**Severity:** Medium  
**Problem:** Accepts any string; a typo silently produces a stat modifier of 0.  
**Fix:**
```python
roll_stat = models.CharField(
    max_length=50, blank=True,
    choices=[(v, v) for v in STAT_FIELD_MAP.values()]
)
```
Add a migration. Add a `clean()` method or constraint if `STAT_FIELD_MAP` is available at model definition time.

---

### 13. Enforce non-blank `ending_type` on ending scenes
**File:** `game/models/world.py`  
**Severity:** Medium  
**Problem:** An ending scene with `ending_type=''` creates a `CompletedQuest` with 0 XP and no error.  
**Fix:** Add a model-level `clean()` that validates `ending_type` is non-blank when `is_ending=True`. Consider a DB constraint.

---

### 14. Replace `LEVEL_UP_FLAVOR` list with dict
**File:** `game/services/progression.py:57` | `game/services/combat.py:118`  
**Severity:** Low  
**Problem:** List indexed by `level - 2` silently produces wrong text or raises `IndexError` if level range changes.  
**Fix:**
```python
LEVEL_UP_FLAVOR = {2: "...", 3: "...", ...}
# usage
LEVEL_UP_FLAVOR.get(new_level, "You feel stronger.")
```

---

### 15. Resolve `resolution_scene` duplication on `Property` / `RivalClaim`
**File:** `game/models/property.py`  
**Severity:** Medium  
**Problem:** `Property.resolution_scene` is copied to `RivalClaim.resolution_scene` at claim creation. If the property's scene later changes, existing claims use stale routing.  
**Fix:** Remove `Property.resolution_scene`. Always route through `RivalClaim.resolution_scene` (set once at creation). Update `property_service.py` callers. Add a migration.

---

### 16. Remove dead fields and code
**Severity:** Low  
Items to delete after confirming no usage:
- `PlayerProperty.upgrade_tier` (`game/models/property.py:26`) — reserved field, never used.
- `Choice.resolve_target` method (`game/models/world.py:200-213`) — dead code, routing goes through `resolve_roll` or direct `.target_scene`.
- `update_scene` `allowed_fields` set (`game/services/quest_builder.py:429-431`) — always-True check, no effect.

---

## Phase 6 — Code Quality & Tests

### 17. Move inline imports to module top-level
**File:** `game/views.py:129,82,434-439,675-678,736-738,836-840`  
**Severity:** Low  
**Fix:** Move all mid-function `from .models.xxx import Xxx` to the top of `views.py`. None of these cause circular imports.

---

### 18. Deduplicate `choice_create` / `choice_panel` context building
**File:** `game/views.py:668-718,740-771`  
**Severity:** Medium  
**Problem:** ~50 lines are near-identical between the two functions. Any future change must be made twice.  
**Fix:** Extract shared context assembly into `_choice_context(choice, session, ...)` and call from both.

---

### 19. Deduplicate `scene_items_save` / `scene_combat_save` double-fetch
**File:** `game/views.py:588,637`  
**Severity:** Low  
**Fix:** Fetch `Scene` once at the top of each function and pass/reuse the result.

---

### 20. Fix hardcoded fixture PKs in tests
**File:** `game/tests.py:50,257`  
**Severity:** Medium  
**Problem:** `Choice.objects.get(pk=5)` and `self.session.current_scene.pk == 22` break silently if fixtures are reloaded.  
**Fix:** Look up by semantic key:
```python
Choice.objects.get(scene__key='...', label__icontains='...')
Scene.objects.get(key='...')
```

---

### 21. Add missing test coverage
**File:** `game/tests.py`  
**Severity:** Medium  
Missing coverage areas identified in audit:
- Property system: `process_turn_income`, `check_rival_contests`, `resolve_contest`
- Flag effects on choices
- `get_effective_stats` passive bonuses
- `award_xp` multi-level crossing

---

## Constants Extract (Cross-Cutting)

### 22. Extract `game_session_id` to a constant
**File:** used in 6+ view functions  
**Fix:** Add to `game/constants.py`:
```python
SESSION_KEY = 'game_session_id'
```
Replace all direct string usages.

---

## Summary Table

| # | Task | Severity | Complexity | Depends On |
|---|------|----------|------------|------------|
| 1 | Fix CombatEncounter routing | Critical | Low | — |
| 2 | `unique_together` on CompletedQuest | High | Low | Migration |
| 3 | Fix RequirementGroup orphan leak | High | Low | — |
| 4 | Move nulling inside transaction | Medium | Low | — |
| 5 | Ownership check in choice_resolve | Medium | Low | — |
| 6 | Externalize SECRET_KEY | Medium | Low | — |
| 7 | Move build_render_context to views | Medium | Medium | — |
| 8 | Strip EventLog writes from combat.py | Medium | Medium | #7 |
| 9 | Extract choice_resolve to service | Medium | High | #7, #8 |
| 10 | Fix N+1 in choice/notice queries | Medium | Medium | — |
| 11 | Fix double queryset eval in property_service | Low | Low | — |
| 12 | Add choices= to Scene.roll_stat | Medium | Low | Migration |
| 13 | Enforce ending_type non-blank | Medium | Low | — |
| 14 | LEVEL_UP_FLAVOR list → dict | Low | Low | — |
| 15 | Consolidate resolution_scene | Medium | Medium | Migration |
| 16 | Remove dead fields/code | Low | Low | — |
| 17 | Move inline imports to top-level | Low | Low | — |
| 18 | Deduplicate choice context building | Medium | Medium | — |
| 19 | Deduplicate scene double-fetch | Low | Low | — |
| 20 | Fix hardcoded PKs in tests | Medium | Low | — |
| 21 | Add missing test coverage | Medium | High | — |
| 22 | Extract SESSION_KEY constant | Low | Low | — |
