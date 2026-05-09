# Quest Authoring Patterns

Canonical quest authoring patterns and examples.

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
- **`award_once=False` on non-consumable SceneItems in a repeatable quest** — player farms persistent gear on every run; set `award_once=True` for non-consumables
- **Arc flag set on scene arrival** — set arc flags on the hub return choice using `set_flag_name`, not in the arrival block
- **Flag cleared in the wrong quest** — if a flag set in Quest N is still needed in Quest N+1, don't clear it on Quest N's hub return; clear it on Quest N+1's hub return choice once it has done its last job
- **Multiple RequirementGroups for mutually exclusive endings** — groups are AND'd; use one group with `logic: any` instead
- **Non-speech choice labels in quotation marks** — quotes on labels are for player dialogue only
- **Body text hard-wrapped at column width** — the `|` scalar preserves every line break; each paragraph must be one continuous line or it breaks mid-sentence in game
- **Roll routing directly to outcome scene** — insert a post-roll confirmation scene for both success and failure paths; routing straight through skips the beat where the result lands (exception: failure path that routes directly to combat can combine confirmation and combat setup in the combat scene body)

