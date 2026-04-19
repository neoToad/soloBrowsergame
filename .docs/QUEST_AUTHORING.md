# Quest Authoring Guide

This document describes how to create quests in this Django text-adventure game. It is intended for LLMs generating quest content or assisting quest authors.

---

## Conceptual Overview

A **Quest** is a directed graph of **Scenes** connected by **Choices**. The player navigates from scene to scene by picking choices. Scenes can award stats, items, contacts, and properties on arrival. Choices can be locked behind requirements. The quest ends when the player reaches a scene with `scene_type='ending'`.

Quests are listed on **hub scenes** via a notice board. The player accepts a quest, enters its `entrance_scene`, and plays through until an ending.

---

## Core Models

### Quest

```
Quest
├── key             SlugField — unique identifier (kebab-case, e.g. "the-warehouse-job")
├── title           CharField — display name
├── description     TextField — shown on the notice board
├── arc             FK → Arc (optional grouping)
├── arc_order       int — sort order within arc
├── entrance_scene  FK → Scene — first scene the player sees
├── hub_scenes      M2M → Scene (hub type) — which hubs post this quest
├── scenes          M2M → Scene — ALL scenes in this quest
├── requirements    M2M → RequirementGroup — player must pass ALL groups to access quest
└── is_repeatable   bool — if True, quest reappears after completion
```

### Scene

```
Scene
├── key             SlugField — unique, format: "{quest_key}__{scene_slug}"
├── scene_type      "normal" | "hub" | "combat" | "ending"
├── title           CharField
├── body            TextField — narrative prose shown to player
├── order           int — display order (lower = earlier)
│
├── ROLL MECHANICS (only when requires_roll=True)
│   ├── requires_roll   bool
│   ├── roll_stat       "muscle" | "reflexes" | "cunning" | "nerve"
│   └── roll_difficulty int — DC to beat (e.g. 12)
│
├── ENDING CONFIG (only when scene_type="ending")
│   └── ending_type  "victory" | "defeat" | "neutral"
│
└── ARRIVAL EFFECTS (applied automatically when player enters)
    ├── cash_change      int — cash delta (negative to take cash away)
    ├── rep_change       int — reputation delta
    ├── heat_change      int — heat delta (clamped to 0 minimum)
    ├── consume_item     FK → Item (optional) — removes one from inventory on arrival
    ├── receive_property FK → Property (optional) — grants property to player
    └── lose_property    FK → Property (optional) — removes property from player
```

### Choice

```
Choice
├── scene           FK → Scene (the scene this choice belongs to)
├── label           CharField — button text the player sees
├── order           int — display order
│
├── ROUTING (use target_scene OR success/failure pair, not both)
│   ├── target_scene    FK → Scene — destination for non-roll scenes
│   ├── success_scene   FK → Scene — destination on roll success
│   └── failure_scene   FK → Scene — destination on roll failure
│
├── NARRATIVE FLAVOR (logged to event log when choice is taken)
│   ├── arrival_flavor          TextField — on success (or any non-roll)
│   └── failure_arrival_flavor  TextField — on roll failure only
│
├── FLAG MANIPULATION (happens when this choice is taken)
│   ├── set_flag_name    CharField — sets this flag on the session
│   └── clear_flag_name  CharField — clears this flag from the session
│
└── requirements    M2M → RequirementGroup — player must pass ALL groups to see choice
```

### SceneItem

Items found in a scene. Processed during arrival.

```
SceneItem
├── scene       FK → Scene
├── item        FK → Item
├── quantity    int
└── award_once  bool — if True, skip award if player already holds this item
```

### SceneContact

Contacts gained or lost in a scene. Processed during arrival.

```
SceneContact
├── scene      FK → Scene
├── contact    FK → Contact
├── action     "gain" | "lose"
└── award_once bool — if True, skip if player already has this contact
```

---

## Stats Reference

| In-game name | DB field   | Description             |
|--------------|------------|-------------------------|
| Muscle       | strength   | Physical power          |
| Reflexes     | agility    | Speed and dodging       |
| Cunning      | intellect  | Thinking and planning   |
| Nerve        | charisma   | Charm and persuasion    |

Player also has: `hp`, `max_hp`, `level` (1–7), `experience`, `cash`, `heat`, `rep`.

---

## Requirements System

Requirements gate access to quests and individual choices. They are structured in two layers:

### RequirementGroup

A group of one or more `Requirement` objects evaluated together.

```
RequirementGroup
├── label    CharField — internal description
├── logic    "all" (AND) | "any" (OR)
└── requirements  M2M → Requirement
```

When multiple `RequirementGroup` objects are attached to a quest or choice, **ALL groups must pass** (AND logic between groups). Within each group, the `logic` field controls whether ALL or ANY requirements must pass.

### Requirement

A single condition checked against the player's current state.

| condition_type      | Uses fields                          | Meaning                           |
|---------------------|--------------------------------------|-----------------------------------|
| `stat_gte`          | `stat_name`, `stat_value`            | Stat (DB name) >= value           |
| `stat_lte`          | `stat_name`, `stat_value`            | Stat (DB name) <= value           |
| `has_item`          | `required_item`                      | Player carries this item          |
| `missing_item`      | `required_item`                      | Player does not carry this item   |
| `quest_completed`   | `required_quest`                     | Quest finished (any ending)       |
| `quest_not_done`    | `required_quest`                     | Quest not finished                |
| `quest_ending`      | `required_quest`, `required_ending_type` | Quest ended as victory/defeat/neutral |
| `level_gte`         | `stat_value`                         | Player level >= value             |
| `xp_gte`            | `stat_value`                         | Player XP >= value                |
| `has_flag`          | `flag_name`                          | Session flag is set               |
| `missing_flag`      | `flag_name`                          | Session flag is not set           |
| `has_contact`       | `required_contact`                   | Player has this contact           |
| `missing_contact`   | `required_contact`                   | Player does not have contact      |

Use `stat_name` with the **DB field name** (`strength`, `agility`, `intellect`, `charisma`), not the in-game alias.

---

## Flag System

Flags are free-form string keys stored per session as a JSON dict (`{flag_name: true}`). They have no predefined list — you invent them as needed.

- **Set a flag**: add `set_flag_name` to a Choice (fires when that choice is taken)
- **Clear a flag**: add `clear_flag_name` to a Choice
- **Check a flag**: add a `Requirement` with `condition_type='has_flag'` or `'missing_flag'`

Flags are used for stateful branching within a quest, e.g. tracking whether the player scouted a location before attacking.

---

## Scene Types and Their Rules

### `normal`

Standard scene. Requires at least one Choice with a `target_scene`.

### `hub`

Central location (e.g., Back Home). Has a notice board listing available quests. Do **not** add hub scenes to individual quests — they are standalone.

### `combat`

Requires a `CombatEncounter` record linking to an `Enemy`. Victory/defeat routing is on the encounter, not the scene's choices. Choices are hidden during active combat.

```
CombatEncounter
├── scene                  OneToOne → Scene
├── enemy                  FK → Enemy
├── victory_scene          FK → Scene
├── defeat_scene           FK → Scene
├── victory_arrival_flavor TextField
└── defeat_arrival_flavor  TextField
```

### `ending`

Terminal scene. Must set `ending_type` to `"victory"`, `"defeat"`, or `"neutral"`. XP is awarded automatically based on ending type (victory=150, neutral=75, defeat=25). Should have a Choice routing back to a hub.

---

## Roll Mechanics

When `scene.requires_roll=True`, the player's chosen action triggers a dice roll:

- Roll: `d20 + floor((stat - 10) / 2)`
- Beat `roll_difficulty` to succeed

Choices in roll scenes use `success_scene`/`failure_scene` instead of `target_scene`. Both must be set.

---

## Arrival Processing Order

When a player enters a scene, the following fires in sequence:

1. Stat changes applied (`cash_change`, `rep_change`, `heat_change`)
2. Property gained or lost (`receive_property`, `lose_property`)
3. `consume_item` removed from inventory
4. Quest completion checked (if `scene_type='ending'`)
5. `SceneItem` records awarded (respects `award_once`)
6. `SceneContact` records processed (gain/lose, respects `award_once`)
7. If quest completed: turn income processed, rival contests triggered, XP awarded

---

## Key Naming Convention

Scene keys must be unique across the entire database. Use the format:

```
{quest_key}__{scene_slug}
```

Example: `the-warehouse-job__scouting-the-roof`

The quest key itself is kebab-case. Hub scene keys use `hub__` as a prefix (e.g. `hub__back_home`).

---

## Minimal Quest Example

This is the smallest valid quest: a two-scene job with a single outcome.

**Quest**: `petty-theft`

**Scenes**:

```
hub__back_home  (existing hub, not part of quest)
    └── notice board → petty-theft

petty-theft__approach        (entrance_scene, normal)
    body: "You spot the mark. Easy money."
    → Choice "Grab it and run" → petty-theft__success

petty-theft__success         (ending, victory)
    body: "You're two hundred richer."
    cash_change: 200
    → Choice "Head home" → hub__back_home
```

---

## Branching Quest Example

A quest with a skill check and two outcomes.

**Scenes**:

```
smuggler-run__the-drop       (entrance_scene, normal, requires_roll=True)
    roll_stat: cunning
    roll_difficulty: 13
    body: "The contact hands you the package. Eyes everywhere."
    → Choice "Play it cool" 
        success_scene → smuggler-run__clean-exit
        failure_scene → smuggler-run__busted
        arrival_flavor: "You walk out like you own the place."
        failure_arrival_flavor: "Your hands give you away."

smuggler-run__clean-exit     (ending, victory)
    body: "Clean drop. The money's already in your account."
    cash_change: 400
    rep_change: 10
    → Choice "Head home" → hub__back_home

smuggler-run__busted         (ending, defeat)
    body: "Cuffs on your wrists. You'll be paying this off for weeks."
    cash_change: -200
    heat_change: 20
    → Choice "Post bail and limp home" → hub__back_home
```

---

## Quest With Gating Requirements

To lock a quest until the player has enough rep:

```
Quest.requirements → RequirementGroup
    logic: "all"
    requirements → Requirement
        condition_type: stat_gte
        stat_name: rep
        stat_value: 50
```

To lock a choice behind a flag set earlier in the same quest:

```
Choice.requirements → RequirementGroup
    logic: "all"
    requirements → Requirement
        condition_type: has_flag
        flag_name: "smuggler_run_has_contact"
```

---

## Combat Quest Pattern

```
ambush__warehouse            (entrance_scene, normal)
    body: "Three of them. You count the exits."
    → Choice "Fight your way through" → ambush__brawl
    → Choice "Look for another way" → ambush__sneak  [gated by reflexes]

ambush__brawl                (combat)
    CombatEncounter:
        enemy: street_thug_x3
        victory_scene: ambush__cleared
        defeat_scene: ambush__knocked_out

ambush__cleared              (ending, victory)
    body: "Bodies on the floor. The package is yours."

ambush__knocked_out          (ending, defeat)
    body: "You wake up in an alley. Wallet gone."
    cash_change: -150
```

---

## Common Mistakes

- **Scene key not in quest.scenes** — the scene exists but is orphaned; the player can never reach it
- **Roll scene with `target_scene`** — use `success_scene`/`failure_scene` instead
- **Non-roll scene with `success_scene`** — only `target_scene` is used on non-roll scenes
- **Ending scene with no exit choice** — player gets stuck; always add a route back to a hub
- **Hub scene inside a quest** — hub scenes are global, not quest-owned; never add them to `quest.scenes`
- **Requirement on `stat_name` using alias** — use the DB field (`strength`, not `muscle`)
- **`award_once=False` on a SceneItem in a repeatable quest** — player farms it on every run; set `award_once=True`