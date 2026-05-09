# Quest Authoring Rules

Canonical structural rules for quest authoring.

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
│   ├── roll_stat       "strength" | "agility" | "intellect" | "charisma"  ← DB field names
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

Consumable heal items (e.g. `zonk_smoked`) can be awarded via `scene_items` on combat outcome scenes — both victory and defeat. In-world this can be loot taken after a win or something pocketed while walking away after a loss. For consumables, set `award_once: false`; unlike persistent gear, repeat runs should still be able to award spendable recovery items.

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

Always use the **DB field name** in code, YAML, and requirements — never the in-game alias. So `roll_stat: charisma` (not `nerve`), `stat_name: strength` (not `muscle`), etc.

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

When a quest's ending needs to gate a later quest in an arc, set the flag on the hub return choice inside the ending scene using `set_flag_name` — not on the scene's arrival block. Arrival effects are reserved for stat and item changes. Every ending scene in a multi-quest arc should have exactly one flag set on its hub return choice corresponding to its outcome.

**Flag hygiene:** Flags should be cleared once they are no longer needed. The right place to clear a flag is on the hub return choice of the quest where the flag last does its job — using `clear_flag_name` on that choice. This keeps `GameSession.flags` clean and prevents stale state accumulating across quests. If a flag set in Quest N is still doing work in Quest N+1, it should not be cleared until Quest N+1's hub return choice. Don't clear a flag in the quest that sets it if a later quest still needs to read it.

---
## Scene Types and Their Rules

### `normal`

Standard scene. Requires at least one Choice with a `target_scene`.

### `hub`

Central location (e.g., Back Home). Has a notice board listing available quests. Do **not** add hub scenes to individual quests — they are standalone.

Hub scenes are returned to repeatedly. Their `body` text must hold up on the first visit and the fiftieth. Do not put story-specific or time-sensitive narration in a hub body. Opening narration and story context belong in a one-time entrance scene inside the first quest, not in the hub itself.

Hub body text follows different rhythm rules than narrative scenes. Where entrance and normal scenes need sentences that connect and build — each one doing something the previous one set up — hub bodies are ambient and environmental. Short declarative sentences are appropriate here because the purpose is texture, not story: establishing a place the player will return to fifty times, not moving them through a situation. The short-sentence rhythm that reads as telegram in a narrative scene reads as atmosphere in a hub.

**Wrong:**
```
body:
  You've been out four days. Your parole officer wants you in a job by the end of the month. Your old crew hasn't called. Then your phone buzzes.
```

**Right:**
```
body:
  Home. Relative term. The radiator clanks. The window looks out on a brick wall. There's a corkboard on the back of the door where you've started pinning job leads. Old habits die. New ones move in.
```

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

Terminal scene. Must set `ending_type` to `"victory"`, `"defeat"`, or `"neutral"`. XP is awarded automatically based on ending type (victory=150, neutral=75, defeat=25). Must have a Choice routing back to a hub.

---
## Roll Mechanics

When `scene.requires_roll=True`, the player's chosen action triggers a dice roll:

- Roll: `d20 + floor((stat - 10) / 2)`
- Beat `roll_difficulty` to succeed

Choices in roll scenes use `success_scene`/`failure_scene` instead of `target_scene`. Both must be set.

Every roll scene must be preceded by a normal scene that establishes the situation — what the player is attempting, what's at stake, and why it's uncertain. The roll scene's body text then narrows focus to the moment of the check itself. The setup scene can be brief (two or three sentences), but the player must understand what they're attempting before the dice roll.

**Wrong:**
```
# Player goes straight from a choice into a roll with no setup
- key: smuggler-run__the-drop
  scene_type: normal
  requires_roll: true
  body: |
    You attempt to play it cool.
```

**Right:**
```
# A normal scene sets the situation first
- key: smuggler-run__the-drop
  scene_type: normal
  requires_roll: false
  body: |
    The contact hands you the package. The lobby is busier than you expected. Two men near the door haven't looked away since you came in. You have to walk past them to get out.

  choices:
    - label: Play it cool
      target_scene: smuggler-run__the-walk-out

# The roll scene focuses on the moment of the check
- key: smuggler-run__the-walk-out
  scene_type: normal
  requires_roll: true
  roll_stat: intellect
  roll_difficulty: 13
  body: |
    You keep your pace even. Don't look at them. The door is twenty feet away.
```
Post-roll confirmation scenes
On both a successful and a failed roll, insert a short normal scene between the roll scene and the outcome scene. This scene surfaces the roll result to the player and lands the moment before consequences play out. It should be two or three sentences at most — enough to close the check, not enough to front-run the outcome.
Body text should open by naming the result directly as a terse in-world note, then land the immediate physical or situational beat:
Success:

Nerve check passed. He holds it for a second. Then something in his posture settles, the way a bluff does when the other person calls it and there's nothing left to protect.

Failure:

Nerve check failed. He laughs — short, sharp, meant to be seen — and calls something over his shoulder. Two guys come off the wall across the street.

Each confirmation scene routes via a single choice to its outcome scene. It carries no arrival effects and sets no flags — it is a beat, not a decision point. The failure_arrival_flavor on the roll choice should still be set, as it fires before the failure confirmation scene loads.

Exception: when the failure path routes directly into a combat scene, the failure confirmation scene and combat setup scene can be the same scene. In that case, keep the confirmation content in the combat scene body (name the failed result and land the immediate beat) before opening the fight setup. Do not skip the confirmation beat.
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

The `title` field of a scene should be the human-readable equivalent of the scene's slug. Capitalise each word, strip hyphens.

| Key | Title |
|-----|-------|
| `the-call__why-you` | `Why You` |
| `smuggler-run__clean-exit` | `Clean Exit` |

---

