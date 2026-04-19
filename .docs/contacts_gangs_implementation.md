# Contacts & Gangs — Implementation Prompts

Work through these in order. Each prompt is self-contained and safe to hand to a fresh conversation.




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