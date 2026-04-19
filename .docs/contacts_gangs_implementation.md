# Contacts & Gangs — Implementation Prompts

Work through these in order. Each prompt is self-contained and safe to hand to a fresh conversation.

---

## 1. Admin — Register Gang and Contact

**Context:** `Gang` and `Contact` models already exist in `game/models/world.py`. `PlayerGangStanding` and `PlayerContact` exist in `game/models/player.py`. Nothing is registered in the Django admin yet.

**Task:** In `game/admin.py`:

1. Add `Gang, Contact, SceneContact, PlayerContact, PlayerGangStanding` to the model imports.

2. Register `GangAdmin`:
   - `list_display = ('key', 'name')`
   - `search_fields = ('key', 'name')`
   - `prepopulated_fields = {'key': ('name',)}`

3. Register `ContactAdmin` — same shape as `GangAdmin`.

4. Add `SceneContactInline(TabularInline)`:
   - model `SceneContact`, fields `('contact', 'action', 'award_once')`, `extra = 0`
   - Add to `SceneAdmin.inlines` alongside the existing `SceneItemInline`

5. Add `PlayerContactInline(TabularInline)`:
   - model `PlayerContact`, fields `('contact', 'acquired_at')`, `readonly_fields = ('acquired_at',)`, `extra = 0`

6. Add `PlayerGangStandingInline(TabularInline)`:
   - model `PlayerGangStanding`, fields `('gang', 'standing')`, `extra = 0`

7. Add both new player inlines to `GameSessionAdmin.inlines`.

8. Update `RequirementAdmin.list_display` — add `'required_contact'`.

9. Update `RequirementInline`:
   - Add `'required_contact'` to `fields` and `readonly_fields`
   - Add an `@admin.display` method for it, matching the pattern of the existing `required_item` display method

---

## 2. Quest Builder Service — `update_scene_contacts`

**Context:** `game/services/quest_builder.py` has `update_scene_items(scene_id, items_data)` at line 625. `SceneContact` is in `game/models/world.py` with fields `scene`, `contact` (FK), `action` (gain/lose), `award_once` (bool).

**Task:** Add `update_scene_contacts(scene_id, contacts_data)` to `quest_builder.py`, directly below `update_scene_items`. It should:

- Accept `contacts_data`: list of dicts with keys `contact_id`, `action`, `award_once`
- Within `transaction.atomic()`: delete all existing `SceneContact` rows for `scene_id`, then recreate from the list
- Skip entries where `contact_id` is blank/None
- Default `action` to `'gain'` if missing or invalid (valid values: `'gain'`, `'lose'`)
- Default `award_once` to `True` if missing
- Return the list of created `SceneContact` objects

Mirror the structure of `update_scene_items` exactly.

---

## 3. Quest Builder Service — Contact requirement support

**Context:** `build_requirement_groups_from_post(obj, post_data)` is at line 668 of `game/services/quest_builder.py`. It already handles `has_item`/`missing_item` with a `required_item_id` lookup. `Requirement` now has a `required_contact` FK and supports condition types `has_contact` and `missing_contact`.

**Task:** In the `for ri in range(req_count)` loop inside `build_requirement_groups_from_post`, add an `elif` branch after the `has_item`/`missing_item` case:

```python
elif ctype in ('has_contact', 'missing_contact'):
    if param:
        try:
            req_kwargs['required_contact_id'] = int(param)
        except ValueError:
            pass
```

No other changes needed in this function.

---

## 4. Quest Builder Views — `scene_panel` contact context

**Context:** `scene_panel` in `game/quest_builder_views.py` (line 110) loads `scene_items` and `all_items` into its context. The template is `admin/quest_builder/partials/scene_panel.html`.

**Task:**

1. Import `Contact` from `..models` at the top of `quest_builder_views.py` (alongside the existing model imports).

2. In `scene_panel`, after the `scene_items` load:
   ```python
   scene_contacts = list(scene.scene_contacts.select_related('contact').order_by('id')) if scene else []
   all_contacts = list(Contact.objects.order_by('name'))
   ```

3. Add both to the context dict alongside `scene_items` / `all_items`.

4. In `choice_requirements_save`, add `'all_contacts': list(Contact.objects.order_by('name'))` to the `render_to_string` context dict so the requirements partial can render a contact dropdown.

---

## 5. Quest Builder Views — `scene_contacts_save`

**Context:** `scene_items_save` in `game/quest_builder_views.py` (line 281) is the pattern to follow. It parses indexed POST keys, calls a service, and re-renders a partial. The service function `update_scene_contacts` will exist after prompt 2 is done.

**Task:** Add `scene_contacts_save(request, quest_id, scene_id)` to `quest_builder_views.py`, directly below `scene_items_save`. It should:

1. Only allow POST; return 405 otherwise.
2. Get `quest` and `scene` via `get_object_or_404`.
3. Parse POST in a loop using keys `contact_id_{n}`, `action_{n}`, `award_once_{n}` (stop when none of the three exist for index `n`). `award_once` should be treated as truthy if the POST key value is `'on'`, `'1'`, `'true'`, or `'yes'` (case-insensitive).
4. Call `update_scene_contacts_service(scene.id, contacts_data)`.
5. Re-render `admin/quest_builder/partials/contacts_section.html` with context: `quest_id`, `scene`, `scene_contacts` (result), `all_contacts` (fresh queryset), `toast_message = 'Contacts saved.'`
6. Return the rendered HTML as `HttpResponse`.

Also add `scene_contacts_save` to the import line in `admin.py` and register the URL in `QuestAdmin.get_urls()`:
```python
path(
    'quest-builder/<int:quest_id>/scene/<int:scene_id>/contacts/save/',
    self.admin_site.admin_view(scene_contacts_save),
    name='quest_builder_scene_contacts_save',
),
```

---

## 6. Template — `contacts_section.html` partial

**Context:** `game/templates/admin/quest_builder/partials/items_section.html` is the pattern. It renders a list of current scene items with a save form that POSTs back via HTMX. The contacts section needs the same shape but with `contact`, `action`, and `award_once` fields instead of `item` and `quantity`.

**Task:** Create `game/templates/admin/quest_builder/partials/contacts_section.html`. It should:

- Mirror the structure of `items_section.html`
- For each existing `SceneContact` in `scene_contacts`, render a row with:
  - A `<select name="contact_id_{n}">` populated from `all_contacts` (show `contact.name`, value = `contact.id`), with the current contact pre-selected
  - A `<select name="action_{n}">` with options `gain` / `lose`, pre-selected to current value
  - A checkbox `<input type="checkbox" name="award_once_{n}">`, checked if current `award_once` is True
- An "Add row" button that appends a blank row (same JS pattern as items section)
- The form POSTs to `{% url 'admin:quest_builder_scene_contacts_save' quest_id scene.id %}` via HTMX (`hx-post`, `hx-target`, `hx-swap` matching the items section pattern)
- Show a toast on success (same pattern as items section)

---

## 7. Template — `scene_panel.html` — add contacts section

**Context:** `game/templates/admin/quest_builder/partials/scene_panel.html` already includes an items section and a combat section as tab panels or collapsible sections. `scene_contacts` and `all_contacts` will now be in context after prompt 4.

**Task:** In `scene_panel.html`, add an include of the contacts section partial alongside the items section:

```django
{% include "admin/quest_builder/partials/contacts_section.html" %}
```

Place it directly below or alongside the items section include, in whatever structure (tab/accordion) the existing sections use.

---

## 8. Template — `requirements_section.html` — contact dropdown

**Context:** `game/templates/admin/quest_builder/partials/requirements_section.html` renders dropdowns/inputs for each requirement type. It already branches on `condition_type` to show item dropdowns for `has_item`/`missing_item` and quest dropdowns for quest types. `all_contacts` will now be in context for the `choice_requirements_save` re-render (after prompt 4).

**Task:** In `requirements_section.html`, add a branch for `has_contact` and `missing_contact` condition types that renders a `<select>` populated from `all_contacts` (value = `contact.id`, label = `contact.name`). The selected value should be the current `requirement.required_contact_id` when editing an existing requirement.

Follow the exact same pattern used for `has_item`/`missing_item` and the item dropdown.