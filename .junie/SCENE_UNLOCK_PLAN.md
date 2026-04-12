# Scene Unlocking System — Implementation Brief

## Audit Summary

All relevant files have been read in full. Key observations that shape this plan:

- The existing `Choice` + `RequirementGroup` system already supports pull-based gating: choices on the hub scene can be hidden until a `quest_completed` requirement passes. **No new model is needed for hub choice gating alone.**
- `SceneUnlock` + `PlayerSceneState` add a complementary push-based layer: completing scene X fires unlock rules that mark new scenes available. These are needed so `complete_scene` can be wired in once and drive future content additions without touching views.
- There is an uncommitted migration in the working tree: `game/migrations/0009_choice_quest_quest_is_repeatable.py`. The new migration for this feature must be `0010_`.
- `maybe_complete_quest` (in `progression.py`) fires when the player reaches an ending scene. `complete_scene` fires on every scene departure — a wider trigger. Both will run in `choice_resolve`; ordering matters (see Conflicts).

---

## Files That Will Change

### `game/models/world.py`
**Add `SceneUnlock` model** — does not touch any existing model.

Fields:
- `from_scene` — FK → `Scene`, `related_name='unlocks'`, `on_delete=CASCADE`
- `unlocks_scene` — FK → `Scene`, `related_name='unlocked_by'`, `on_delete=CASCADE`
- `requires_choice` — FK → `Choice`, null/blank, `related_name='triggers_unlocks'`, `on_delete=SET_NULL`
  *(If set, this unlock only fires when the player took this specific choice out of `from_scene`.)*
- `requires_item` — FK → `Item`, null/blank, `related_name='+'`, `on_delete=SET_NULL`
  *(If set, player must have this item in inventory at completion time.)*

Do **not** add `requires_rep` — no rep system exists. Omit this field entirely.

---

### `game/models/player.py`
**Add `PlayerSceneState` model** — does not touch any existing model.

Fields:
- `session` — FK → `GameSession`, `related_name='scene_states'`, `on_delete=CASCADE`
- `scene` — FK → `Scene`, `related_name='player_states'`, `on_delete=CASCADE`
- `state` — `CharField(max_length=20)`, choices: `('locked', 'available', 'completed')`, default `'available'`

Constraint: `unique_together = ('session', 'scene')`

---

### `game/models/__init__.py`
Add to imports and re-exports:
- `SceneUnlock` (from `world`)
- `PlayerSceneState` (from `player`)

---

### Migration `game/migrations/0010_sceneunlock_playerscenestate.py`
Auto-generated via `makemigrations`. Must depend on `0009`. Do not write by hand.

---

### `game/admin.py`

**Import** `SceneUnlock`, `PlayerSceneState` into the existing import block.

**Add `SceneUnlockAdmin`:**
```python
@admin.register(SceneUnlock)
class SceneUnlockAdmin(admin.ModelAdmin):
    list_display = ('from_scene', 'unlocks_scene', 'requires_choice', 'requires_item')
    list_select_related = True
    autocomplete_fields = ('from_scene', 'unlocks_scene', 'requires_choice', 'requires_item')
```

**Add `PlayerSceneStateAdmin`:**
```python
@admin.register(PlayerSceneState)
class PlayerSceneStateAdmin(admin.ModelAdmin):
    list_display = ('session', 'scene', 'state')
    list_filter = ('state',)
    list_select_related = True
```

---

### `game/services/scene.py`
Add three functions below the existing `get_available_choices`.

**`unlock_scene(session, scene) → None`**
- `PlayerSceneState.objects.get_or_create(session=session, scene=scene, defaults={'state': 'available'})`
- If the row already exists with `state='locked'`, update it to `'available'`.
- Returns nothing.

**`complete_scene(session, scene, choice, inventory) → list[str]`**
- `get_or_create` a `PlayerSceneState` for `(session, scene)` and set `state='completed'`.
- Query `SceneUnlock.objects.filter(from_scene=scene).select_related('requires_item')`.
- For each unlock rule:
  - If `unlock.requires_choice` is set and `unlock.requires_choice_id != choice.id`: skip.
  - If `unlock.requires_item` is set and `unlock.requires_item_id not in inventory`: skip.
  - Call `unlock_scene(session, unlock.unlocks_scene)`.
  - Append a log string: `f"New area unlocked: {unlock.unlocks_scene.title}."` to the result list.
- Returns the list of log strings (may be empty). **Does not create `EventLog` entries.**

**`get_available_scenes(session) → QuerySet[Scene]`**
- Returns `Scene.objects.filter(player_states__session=session, player_states__state='available')`.
- Used by the hub template or any view that needs to list unlocked scenes outside of choices.

*Do not modify `get_available_choices`.* Hub choice gating continues to use the existing RequirementGroup path.

---

### `game/views.py` — `choice_resolve`

**Import** `complete_scene` from `game.services.scene`.

**Wire in `complete_scene`** immediately after the session is advanced to `next_scene` and before `maybe_complete_quest`. Insert between the "ADVANCE SESSION" block and the "QUEST COMPLETION" block:

```python
# SCENE UNLOCK
unlock_logs = complete_scene(session, scene, choice, inventory)
for log_text in unlock_logs:
    EventLog.objects.create(session=session, text=log_text)
```

`scene` here is the scene the player is leaving (already assigned from `choice.scene` at line 89). `inventory` is already in scope.

**No other changes to `choice_resolve`.** No changes to `game_hub`, `scene_detail`, `combat_attack`, `level_up`, or `use_item`.

---

### `templates/game/partials/scene_panel.html`
**No changes required in this commit.** Hub choice filtering already works via `get_available_choices` + RequirementGroup. The five-partial HTMX response already re-renders the scene panel on every turn, so newly visible hub choices appear automatically after quest completion.

A future commit may add hub-specific layout (e.g., grouping quest-entry choices differently), but that is explicitly out of scope here.

---

## Conflicts and Risks

### 1. Dual gating systems — decision required before implementation
Hub choices can be gated by **RequirementGroup** (pull, existing) or by **PlayerSceneState** (push, new). These are independent mechanisms. **Do not couple them.** The rule is:

- Hub quest-entry choices: gate with RequirementGroup (`quest_completed` condition). No `PlayerSceneState` involved.
- Non-hub scene discovery (unlocking hidden areas after a scene event): use `SceneUnlock` + `PlayerSceneState` + `get_available_scenes`.

Do not add `PlayerSceneState` checks inside `get_available_choices`. The two mechanisms must not know about each other.

### 2. `complete_scene` fires on every departure — broad trigger
`complete_scene` will fire when the player leaves *any* scene, not just ending scenes. This is intentional (scene-level events), but means it runs even when traveling through normal mid-quest scenes. Performance impact is bounded by the number of `SceneUnlock` rows for that scene — will be zero for most scenes during early development.

### 3. Ordering in `choice_resolve`
The correct execution order is:
1. Roll (if required)
2. Log roll result
3. Arrival flavor log
4. Consume item
5. Advance session to `next_scene`
6. **`complete_scene(session, scene, choice, inventory)`** ← new, fires on departure from `scene`
7. `maybe_complete_quest(session, stats, next_scene, completed_map)`
8. `award_scene_items`

`complete_scene` must fire before `maybe_complete_quest` because unlock rules are about the scene just left, not the scene arrived at. `completed_map` is still the old map at this point (quest not yet marked done), which is correct — `SceneUnlock` checks inventory, not quest state.

### 4. `completed_map` is stale during `complete_scene`
`load_session_context` builds `completed_map` before any state changes. If a future `SceneUnlock` rule needs to check quest completion, it would see the pre-turn state. This is acceptable and consistent with how RequirementGroup evaluation works elsewhere — do not reload `completed_map` mid-request.

### 5. `PlayerSceneState` vs `CompletedQuest` — do not conflate
Quest completion tracking uses `CompletedQuest` (for RequirementGroup `quest_completed` checks). Scene completion tracking uses `PlayerSceneState`. They are separate concerns. Do not use `PlayerSceneState` as a substitute for `CompletedQuest`.

### 6. Hub template does not differentiate hub vs. non-hub rendering
`scene_panel.html` renders all scenes identically. If the hub needs a distinct visual layout (e.g., card-style quest entries rather than a list of buttons), that requires a `{% if scene.is_hub %}` branch added to `scene_panel.html`. That is a separate future commit — do not include it here.

### 7. `requires_rep` — omit entirely
The plan mentioned this field. There is no reputation system in the codebase. Adding a field with no backing logic would create dead schema. Leave it out.

---

## Build Order

Follow the project convention exactly. Never combine steps.

```
Commit 1: Models + migration
  game/models/world.py      — add SceneUnlock
  game/models/player.py     — add PlayerSceneState
  game/models/__init__.py   — export both
  game/admin.py             — register both
  game/migrations/0010_...  — auto-generated

Commit 2: Service functions
  game/services/scene.py    — add unlock_scene, complete_scene, get_available_scenes

Commit 3: Wire into view
  game/views.py             — import complete_scene, call it in choice_resolve

Commit 4: Template (deferred)
  No template changes are required for the core system.
  If hub-specific layout is added later, it gets its own commit.
```

---

## Data Design Note

### What rows to create to wire Quest 1 → Quest 2 discovery through the hub

Assuming the existing fixture has:
- Hub scene `hub__main_square`
- Quest 1 with key `warehouse_job` and an entrance scene `warehouse_job__entrance`
- Quest 2 with key `<tbd>` and an entrance scene `<tbd>__entrance`

#### Step 1 — Ensure Quest 1 entry choice exists on the hub

Create a `Choice`:
- `scene = hub__main_square`
- `label = "<Quest 1 hook text>"`
- `target_scene = warehouse_job__entrance`
- `quest = Quest1` ← hides once Quest 1 is completed (unless repeatable)
- `requirements = []` ← always visible

This may already exist in `hub.json`. Verify before creating.

#### Step 2 — Create the Quest 2 entry choice on the hub (gated)

Create a `Requirement`:
- `condition_type = 'quest_completed'`
- `required_quest = Quest1`

Create a `RequirementGroup`:
- `label = "Quest 1 complete"`
- `logic = 'all'`
- `requirements = [<the Requirement above>]`

Create a `Choice`:
- `scene = hub__main_square`
- `label = "<Quest 2 hook text — NPC dialogue, notice, opportunity>"`
- `target_scene = <quest2>__entrance`
- `quest = Quest2` ← hides once Quest 2 is completed (unless repeatable)
- `requirements = [<the RequirementGroup above>]`

#### Step 3 — SceneUnlock rows (optional, for push-based unlock)

`SceneUnlock` rows are *not* required for the hub choice gating described above — RequirementGroup handles it at render time. Add `SceneUnlock` rows only if completing a scene should proactively push a notification or unlock a non-choice scene. For example:

- `from_scene = warehouse_job__ending_victory, unlocks_scene = <some_new_area_scene>` — unlocks a hidden location after Quest 1 victory. This is a good first test of the push system and should be created in the admin after Commit 1.

#### Summary table

| Object | Key / Label | Purpose |
|--------|-------------|---------|
| `Choice` | hub → Quest1 entrance | Always-visible Quest 1 entry on hub |
| `Requirement` | `quest_completed / Quest1` | Condition for Quest 2 gating |
| `RequirementGroup` | "Quest 1 complete" | Groups the condition |
| `Choice` | hub → Quest2 entrance, requires group | Quest 2 appears after Quest 1 done |
| `SceneUnlock` | Quest1 ending → new area | Optional first push-unlock test |
