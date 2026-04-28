# Quest Authoring Guide

This document covers the structural rules for quest authoring: models, scene types, routing, requirements, flags, YAML formatting, and common mistakes. It is intended for LLMs generating quest content or assisting quest authors.

**Before writing any prose** — scene body text, arrival flavors, choice labels — read `QUEST_CONTENT_GUIDE.md`. That document defines tone, sentence rhythm, character voice, dialogue conventions, and the scene-level writing checklist. Both documents are equally binding.

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

## Writing Conventions

### Hub return choices must have arrival flavor

Any choice that routes the player back to a hub scene must have `arrival_flavor` set. This acts as the closing beat of the quest. Leaving it blank makes the quest feel like it cuts out rather than ends. This applies to both victory and defeat ending scenes.

**Wrong:**
```
Choices:
  1. label:        "Back to the apartment"
     target_scene: hub__apartment
     order: 1
```

**Right:**
```
Choices:
  1. label:        "Back to the apartment"
     target_scene: hub__apartment
     arrival_flavor: "The walk back is quiet. That's fine."
     order: 1
```

### Body text line breaks

Each paragraph in a `body` field must be a single continuous line in the YAML file, no matter how long. The YAML `|` block scalar preserves every line break literally — hard-wrapping a sentence across two lines for readability causes a mid-sentence break in-game.

Paragraph breaks are represented by a single blank line between paragraphs, which `|` stores as `\n\n`. That double newline is the only intentional line break in body text.

**Wrong (hard-wrapped — breaks mid-sentence in game):**
```yaml
body: |
  Morris calls at seven in the morning, which already tells you something — Morris
  is a noon-at-the-earliest kind of person, and a seven a.m. call means either
  the job is time-sensitive or something went wrong upstream.

  He doesn't explain which.
```

**Right (each paragraph is one unbroken line):**
```yaml
body: |
  Morris calls at seven in the morning, which already tells you something — Morris is a noon-at-the-earliest kind of person, and a seven a.m. call means either the job is time-sensitive or something went wrong upstream.

  He doesn't explain which.
```

This applies to all `body` fields on scenes. It also applies to `arrival_flavor` and `failure_arrival_flavor`, though those are single sentences and the problem rarely arises there.

When converting a markdown spec to YAML, never introduce line breaks inside a paragraph to fit a column width. The spec may have prose wrapped at 80 characters for readability — do not carry that wrapping into the YAML output. Unwrap each paragraph into a single line before writing it to the `body` block.

### Branching on prior quest outcomes

When two paths through a quest diverge based on a prior quest's outcome, use a single entrance scene with `quest_ending` requirements on the choices rather than creating two separate quests. The entrance body text must be written neutrally — true for both players regardless of which path they're on.

**Wrong:**
```
# Two separate quests for the same story beat
quest: the-fence-with-jewels
quest: the-fence-without-jewels
```

**Right:**
```
# One quest, one entrance scene, requirements on the choices
- key: the-fence__intro
  choices:
    - label: Head to Marek's
      requirements:
        - label: Clean or rough exit
          logic: any
          conditions:
            - condition_type: quest_ending
              required_quest: the-box
              required_ending_type: victory
            - condition_type: quest_ending
              required_quest: the-box
              required_ending_type: neutral

    - label: Hit the evidence lockup first
      requirements:
        - label: Got busted
          logic: all
          conditions:
            - condition_type: quest_ending
              required_quest: the-box
              required_ending_type: defeat
```

### Multi-quest arc gating

Use `quest_ending` rather than `quest_completed` when the downstream quest cares about *how* the prior quest ended. Use `quest_completed` only when any ending is an acceptable prerequisite.

When a quest accepts multiple valid prior endings, use a single `RequirementGroup` with `logic: any` and one condition per accepted ending type. Do not create separate requirement groups for this — multiple groups are AND'd together, which will never pass for mutually exclusive endings.

**Accepts any ending:**
```
requirements:
  - label: Must have completed the box
    logic: all
    conditions:
      - condition_type: quest_completed
        required_quest: the-box
```

**Accepts specific endings only:**
```
requirements:
  - label: Must have gotten out of the fence
    logic: any
    conditions:
      - condition_type: quest_ending
        required_quest: the-fence
        required_ending_type: victory
      - condition_type: quest_ending
        required_quest: the-fence
        required_ending_type: neutral
```

**Accepts only one specific ending:**
```
requirements:
  - label: Must have been defeated by the fence
    logic: all
    conditions:
      - condition_type: quest_ending
        required_quest: the-fence
        required_ending_type: defeat
```

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
       arrival_flavor: "You count it twice. Still two hundred."
```

---

## Branching Quest Example

A quest with a skill check and two outcomes.

**Scenes**:

```
smuggler-run__the-drop       (entrance_scene, normal)
    body: "The contact hands you the package. The lobby is busier
           than expected. Two men near the door haven't looked away."
    → Choice "Play it cool" → smuggler-run__the-walk-out

smuggler-run__the-walk-out   (normal, requires_roll=True)
    roll_stat: intellect
    roll_difficulty: 13
    body: "You keep your pace even. Don't look at them. The door
           is twenty feet away."
    → Choice "Keep moving"
        success_scene → smuggler-run__clean-exit
        failure_scene → smuggler-run__busted
        arrival_flavor: "You walk out like you own the place."
        failure_arrival_flavor: "Your hands give you away."

smuggler-run__clean-exit     (ending, victory)
    body: "Clean drop. The money's already in your account."
    cash_change: 400
    rep_change: 10
    → Choice "Head home" → hub__back_home
       arrival_flavor: "Morris says acceptable. You take it."

smuggler-run__busted         (ending, defeat)
    body: "Cuffs on your wrists. You'll be paying this off for weeks."
    cash_change: -200
    heat_change: 20
    → Choice "Post bail and limp home" → hub__back_home
       arrival_flavor: "The walk home is longer than it should be."
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
    → Choice "Look for another way" → ambush__sneak  [gated by agility]

ambush__brawl                (combat)
    CombatEncounter:
        enemy: street_thug_x3
        victory_scene: ambush__cleared
        defeat_scene: ambush__knocked_out

ambush__cleared              (ending, victory)
    body: "Bodies on the floor. The package is yours."
    → Choice "Get out" → hub__back_home
       arrival_flavor: "You don't run. Running draws attention."

ambush__knocked_out          (ending, defeat)
    body: "You wake up in an alley. Wallet gone."
    cash_change: -150
    → Choice "Walk it off" → hub__back_home
       arrival_flavor: "Three cracked ribs. You've had worse. Barely."
```

---

## Common Mistakes

- **Scene key not in quest.scenes** — the scene exists but is orphaned; the player can never reach it
- **Roll scene with `target_scene`** — use `success_scene`/`failure_scene` instead
- **Non-roll scene with `success_scene`** — only `target_scene` is used on non-roll scenes
- **Roll scene with no preceding setup scene** — always establish the situation in a normal scene first
- **Ending scene with no exit choice** — player gets stuck; always add a route back to a hub
- **Ending scene hub return choice with no `arrival_flavor`** — quest cuts out rather than ends; always set it
- **Hub scene inside a quest** — hub scenes are global, not quest-owned; never add them to `quest.scenes`
- **Hub scene body with story-specific narration** — hub bodies must be reusable across all visits
- **Requirement on `stat_name` using alias** — use the DB field (`strength`, not `muscle`; `charisma`, not `nerve`)
- **`roll_stat` using in-game alias** — use the DB field (`charisma`, not `nerve`)
- **`award_once=False` on a SceneItem in a repeatable quest** — player farms it on every run; set `award_once=True`
- **Arc flag set on scene arrival** — set arc flags on the hub return choice using `set_flag_name`, not in the arrival block
- **Multiple RequirementGroups for mutually exclusive endings** — groups are AND'd; use one group with `logic: any` instead
- **Non-speech choice labels in quotation marks** — quotes on labels are for player dialogue only
- **Body text hard-wrapped at column width** — the `|` scalar preserves every line break; each paragraph must be one continuous line or it breaks mid-sentence in game
