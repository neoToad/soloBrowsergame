# Contacts & Gangs — Implementation Prompts

Work through these in order. Each prompt is self-contained and safe to hand to a fresh conversation.




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