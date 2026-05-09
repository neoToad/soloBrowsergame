# Quest YAML Import Pipeline

This document covers the YAML schema for quest authoring and the import pipeline that loads quests into the Django database. It is a technical companion to `QUEST_AUTHORING.md` and `QUEST_AUTHORING_AMENDMENTS.md`.

---

## Pipeline Overview

```
1. Author quest in markdown in chat
2. Claude converts markdown to YAML using this schema
3. Save YAML file to project (e.g. quests/the-call.yaml)
4. Run: python manage.py import_quest quests/the-call.yaml
5. Importer creates all DB records in the correct order
```

Claude sits in the middle as a conversion layer. You never write YAML by hand — the markdown spec format is your authoring interface, YAML is the machine's interface. The authoring docs define both sides of that contract.

---

## Import Order

The importer must create records in this order to resolve foreign key references correctly:

1. `Quest` record (no FK dependencies at creation time)
2. All `Scene` records (body/config only, no FKs yet)
3. `Quest.entrance_scene` FK resolved and saved
4. All `Choice` records with FKs resolved (`target_scene`, `success_scene`, `failure_scene`)
5. All `RequirementGroup` and `Requirement` records — attached to quests and choices
6. All `SceneItem` records
7. All `SceneContact` records
8. All `CombatEncounter` records
9. `Quest.scenes` M2M populated
10. `Quest.hub_scenes` M2M populated

---

## Create vs Update

The importer uses Django's `update_or_create` keyed on `key` for quests and scenes, and on `scene` + `label` + `order` for choices. Re-running the importer on an edited YAML file updates existing records rather than duplicating them. This means YAML files are the source of truth — edits should always be made in the YAML, not in the Django admin.

---

## Schema Conventions

- Every field is always present. Use `null` for unused fields rather than omitting them. This keeps the importer simple — it never has to handle missing keys.
- `body` always uses the YAML block scalar (`|`) to preserve paragraph breaks. Each paragraph must be written as a single continuous line — never hard-wrap at a column width. Blank lines between paragraphs become `\n\n` in the DB. That double newline is the only intentional line break; all other wrapping is the renderer's job.
- All scene and quest references use `key` strings. The importer resolves them to FK relationships after all scenes are created.
- `requirements` is a list of `RequirementGroup` objects. Multiple groups means ALL groups must pass (AND between groups). Within each group, `logic` controls AND/OR between individual conditions.
- `combat_encounter` is only present on scenes with `scene_type: combat`. The importer ignores it on all other scene types.
- `roll` block is always present but `requires_roll: false` means the importer ignores `roll_stat` and `roll_difficulty`.
- `arrival` supports territory and gang standing effects:
  - `receive_territory` (territory key or `null`)
  - `lose_territory` (territory key or `null`)
  - `discover_territory` (territory key or `null`)
  - `gang_standing_changes` (list, default `[]`)

---

## Full YAML Schema

Below is the complete `the-call` quest as a working reference example covering every field and scene type.

```yaml
quest:
  key: the-call
  title: The Call
  description: >
    Your sister reached out. First time in three years.
    She needs something taken care of. Family's family.
  arc: null
  arc_order: null
  is_repeatable: false
  hub_scenes:
    - hub__apartment
  entrance_scene: the-call__four-days-out
  requirements: []

scenes:

  # -------------------------
  # ENTRANCE SCENE
  # -------------------------

  - key: the-call__four-days-out
    scene_type: normal
    title: Four Days Out
    order: 10
    body: |
      Three years inside and the city didn't wait for you. The apartment
      is exactly how you left it — which means it's a mess. Water stain
      on the ceiling shaped like a boot. Radiator that clanks like it's
      got opinions. The envelope of cash you came home with is already
      half gone and your parole officer wants you in legitimate work by
      the end of the month.

      Your old crew hasn't called.

      Then your phone buzzes. Your sister's name on the screen. You
      haven't spoken since the trial. Three years of silence and she's
      calling at nine on a Tuesday night. You stare at it for two rings.

    roll:
      requires_roll: false
      roll_stat: null
      roll_difficulty: null

    ending:
      ending_type: null

    arrival:
      cash_change: 0
      rep_change: 0
      heat_change: 0
      consume_item: null
      receive_property: null
      lose_property: null

    scene_items: []
    scene_contacts: []

    choices:
      - label: Answer it
        order: 1
        target_scene: the-call__her-voice
        success_scene: null
        failure_scene: null
        arrival_flavor: You pick up. Neither of you says anything for a moment.
        failure_arrival_flavor: null
        set_flag_name: null
        clear_flag_name: null
        requirements: []

      - label: Let it ring out
        order: 2
        target_scene: the-call__her-voice
        success_scene: null
        failure_scene: null
        arrival_flavor: It goes to voicemail. Twenty seconds later, a text. I need help. Please.
        failure_arrival_flavor: null
        set_flag_name: null
        clear_flag_name: null
        requirements: []

  # -------------------------
  # NORMAL SCENE
  # -------------------------

  - key: the-call__her-voice
    scene_type: normal
    title: Her Voice
    order: 20
    body: |
      She doesn't say hello. Just launches into it like she's been
      rehearsing. There's a guy — Terrell — been coming around her
      building. Says she owes him for something her neighbor ran up.
      Wrong place, wrong association. Doesn't matter how it started.
      What matters is he's been at her door twice this week and the
      second time he put his hand on the frame and leaned in.

      You ask if she's okay. Long pause.

      She says she's fine. She just needs it to stop.

      Another pause. Longer.

      She didn't want to call you. She wants you to know that.

    roll:
      requires_roll: false
      roll_stat: null
      roll_difficulty: null

    ending:
      ending_type: null

    arrival:
      cash_change: 0
      rep_change: 0
      heat_change: 0
      consume_item: null
      receive_property: null
      lose_property: null

    scene_items: []
    scene_contacts: []

    choices:
      - label: Tell her you'll handle it
        order: 1
        target_scene: the-call__terrell
        success_scene: null
        failure_scene: null
        arrival_flavor: She hangs up before you can say anything else.
        failure_arrival_flavor: null
        set_flag_name: null
        clear_flag_name: null
        requirements: []

      - label: Ask her why she called you specifically
        order: 2
        target_scene: the-call__why-you
        success_scene: null
        failure_scene: null
        arrival_flavor: Silence. Then she says you owe her one. You owe her about a thousand.
        failure_arrival_flavor: null
        set_flag_name: null
        clear_flag_name: null
        requirements: []

  # -------------------------
  # CONVERGING SCENE (one beat, rejoins main path)
  # -------------------------

  - key: the-call__why-you
    scene_type: normal
    title: Why You
    order: 30
    body: |
      She lets the silence sit for a moment, like she's deciding how
      honest to be.

      Because there's nobody else. Because you're already the worst
      thing that could happen to someone, so what's one more time.

      It lands like she meant it to. You don't argue. There's nothing
      to argue with.

    roll:
      requires_roll: false
      roll_stat: null
      roll_difficulty: null

    ending:
      ending_type: null

    arrival:
      cash_change: 0
      rep_change: 0
      heat_change: 0
      consume_item: null
      receive_property: null
      lose_property: null

    scene_items: []
    scene_contacts: []

    choices:
      - label: Tell her you'll handle it
        order: 1
        target_scene: the-call__terrell
        success_scene: null
        failure_scene: null
        arrival_flavor: She hangs up. You sit with it for a minute before you move.
        failure_arrival_flavor: null
        set_flag_name: null
        clear_flag_name: null
        requirements: []

  # -------------------------
  # BRANCHING SCENE (player chooses approach)
  # -------------------------

  - key: the-call__terrell
    scene_type: normal
    title: Terrell
    order: 40
    body: |
      Your sister's building is a six-story walkup off Decker Avenue.
      Terrell isn't hard to find — he's exactly where she said he'd be,
      leaning against the stoop railing like he owns the block. Young.
      Maybe twenty-five. Gold chain, clean sneakers, eyes that clock you
      the second you round the corner.

      He watches you approach without moving. You lost?

    roll:
      requires_roll: false
      roll_stat: null
      roll_difficulty: null

    ending:
      ending_type: null

    arrival:
      cash_change: 0
      rep_change: 0
      heat_change: 0
      consume_item: null
      receive_property: null
      lose_property: null

    scene_items: []
    scene_contacts: []

    choices:
      - label: Talk him down
        order: 1
        target_scene: the-call__squeeze
        success_scene: null
        failure_scene: null
        arrival_flavor: You keep your voice low. Make sure he has to lean in to hear you.
        failure_arrival_flavor: null
        set_flag_name: null
        clear_flag_name: null
        requirements: []

      - label: Don't waste words
        order: 2
        target_scene: the-call__the-fight
        success_scene: null
        failure_scene: null
        arrival_flavor: You close the distance before he finishes the sentence.
        failure_arrival_flavor: null
        set_flag_name: null
        clear_flag_name: null
        requirements: []

  # -------------------------
  # ROLL SCENE
  # -------------------------

  - key: the-call__squeeze
    scene_type: normal
    title: Squeeze
    order: 50
    body: |
      You tell him who you're there for. Then you tell him — quietly,
      without any particular emotion — what happens if he comes back.
      You don't raise your voice. You don't need to. The trick is
      making sure he understands that you mean it more than he does.

    roll:
      requires_roll: true
      roll_stat: charisma
      roll_difficulty: 11

    ending:
      ending_type: null

    arrival:
      cash_change: 0
      rep_change: 0
      heat_change: 0
      consume_item: null
      receive_property: null
      lose_property: null

    scene_items: []
    scene_contacts: []

    choices:
      - label: Let him think about it
        order: 1
        target_scene: null
        success_scene: the-call__backed-off
        failure_scene: the-call__the-fight
        arrival_flavor: Something shifts behind his eyes. He nods, once, and steps back.
        failure_arrival_flavor: He laughs. Calls something over his shoulder. Two guys emerge from the alley.
        set_flag_name: null
        clear_flag_name: null
        requirements: []

  # -------------------------
  # COMBAT SCENE
  # -------------------------

  - key: the-call__the-fight
    scene_type: combat
    title: The Fight
    order: 60
    body: |
      It goes loud and fast. Terrell's got reach but no discipline.
      The stoop light flickers. Somewhere above you a window slides shut.

    roll:
      requires_roll: false
      roll_stat: null
      roll_difficulty: null

    ending:
      ending_type: null

    arrival:
      cash_change: 0
      rep_change: 0
      heat_change: 0
      consume_item: null
      receive_property: null
      lose_property: null

    scene_items: []
    scene_contacts: []
    choices: []

    combat_encounter:
      enemy: terrell
      victory_scene: the-call__backed-off
      defeat_scene: the-call__beaten
      victory_arrival_flavor: Terrell's on the ground. He's breathing. That's generous of you.
      defeat_arrival_flavor: The pavement comes up fast. Last thing you hear is footsteps leaving.

  # -------------------------
  # SCENE WITH ITEMS AND CONTACTS
  # -------------------------

  - key: the-call__backed-off
    scene_type: normal
    title: Backed Off
    order: 70
    body: |
      Terrell gets the message. However it was delivered.

      You go through his pockets before he has a chance to reconsider.
      A hundred and fifty in crumpled bills and a pair of brass knuckles
      with somebody else's initials scratched into the base. You pocket
      both. He doesn't object.

      You text your sister two words. It's done.

      She doesn't reply. But she reads it. You see the tick.

    roll:
      requires_roll: false
      roll_stat: null
      roll_difficulty: null

    ending:
      ending_type: null

    arrival:
      cash_change: 150
      rep_change: 0
      heat_change: 0
      consume_item: null
      receive_property: null
      lose_property: null

    scene_items:
      - item: brass_knuckles
        quantity: 1
        award_once: true

    scene_contacts:
      - contact: sister
        action: gain
        award_once: true

    choices:
      - label: Go home
        order: 1
        target_scene: the-call__done
        success_scene: null
        failure_scene: null
        arrival_flavor: The walk back is quiet. That's fine.
        failure_arrival_flavor: null
        set_flag_name: null
        clear_flag_name: null
        requirements: []

  # -------------------------
  # VICTORY ENDING
  # -------------------------

  - key: the-call__done
    scene_type: ending
    title: Done
    order: 80
    body: |
      Back in the apartment. Radiator clanking. The city outside doing
      what it always does. You set the brass knuckles on the counter
      and count the cash. A hundred and fifty. Not bad for a Tuesday.

      Your sister still hasn't texted back. But she will. Eventually.
      People always come back when they need something. The trick is
      being someone worth coming back to.

      The corkboard on the back of the door has one job pinned to it.
      Could be worse starts.

    roll:
      requires_roll: false
      roll_stat: null
      roll_difficulty: null

    ending:
      ending_type: victory

    arrival:
      cash_change: 0
      rep_change: 10
      heat_change: 0
      consume_item: null
      receive_property: null
      lose_property: null

    scene_items: []
    scene_contacts: []

    choices:
      - label: Back to the apartment
        order: 1
        target_scene: hub__apartment
        success_scene: null
        failure_scene: null
        arrival_flavor: You hang your jacket up. First time in three years that felt normal.
        failure_arrival_flavor: null
        set_flag_name: null
        clear_flag_name: null
        requirements: []

  # -------------------------
  # DEFEAT ENDING
  # -------------------------

  - key: the-call__beaten
    scene_type: ending
    title: Beaten
    order: 90
    body: |
      You come to on the pavement outside your sister's building. Ribs
      aching, wallet lighter. Someone took the liberty.

      You don't go up. You can't face that conversation right now.
      You just walk. The city swallows you up the way it always does —
      indifferent, unhurried, completely unimpressed.

      Your phone has no new messages.

    roll:
      requires_roll: false
      roll_stat: null
      roll_difficulty: null

    ending:
      ending_type: defeat

    arrival:
      cash_change: -25
      rep_change: -5
      heat_change: 10
      consume_item: null
      receive_property: null
      lose_property: null

    scene_items: []
    scene_contacts: []

    choices:
      - label: Back to the apartment
        order: 1
        target_scene: hub__apartment
        success_scene: null
        failure_scene: null
        arrival_flavor: You take the long way. Nobody should see you like this.
        failure_arrival_flavor: null
        set_flag_name: null
        clear_flag_name: null
        requirements: []
```

---

## Requirements Schema Reference

Requirements are not used in `the-call` but are included here as a reference for future quests.

### On a choice (flag gate):

```yaml
    choices:
      - label: "Tell him you know about the skimming"
        order: 1
        target_scene: the-corner-job__pays-up
        success_scene: null
        failure_scene: null
        arrival_flavor: The color drains out of his face. He pays.
        failure_arrival_flavor: null
        set_flag_name: null
        clear_flag_name: null
        requirements:
          - label: Must have scouted
            logic: all
            conditions:
              - condition_type: has_flag
                flag_name: corner_job_scouted
                stat_name: null
                stat_value: null
                required_item: null
                required_quest: null
                required_ending_type: null
                required_contact: null
```

### On a quest (completion gate):

```yaml
quest:
  key: the-corner-job
  requirements:
    - label: Must have completed the call
      logic: all
      conditions:
        - condition_type: quest_completed
          required_quest: the-call
          flag_name: null
          stat_name: null
          stat_value: null
          required_item: null
          required_ending_type: null
          required_contact: null
```

---

## Arrival Territory and Gang Standing Schema

Use these fields inside each scene's `arrival` block when needed:

```yaml
arrival:
  cash_change: 0
  rep_change: 0
  heat_change: 0
  consume_item: null
  receive_property: null
  lose_property: null
  receive_territory: null
  lose_territory: null
  discover_territory: null
  gang_standing_changes: []
```

Gang standing entries use this shape:

```yaml
arrival:
  gang_standing_changes:
    - gang: dockers_union
      standing_change: 5
    - gang: southside_kings
      standing_change: -3
```

---

## Importer Command

The importer lives at:

```
yourapp/management/commands/import_quest.py
```

Run it with:

```bash
python manage.py import_quest quests/the-call.yaml
```

It uses `update_or_create` keyed on `key` for quests and scenes, and on `scene` + `label` + `order` for choices. Re-running on an edited YAML file updates existing records safely. The YAML file is the source of truth — always edit there, not in the Django admin.

---

## Claude Conversion Prompt

When converting a markdown quest spec to YAML, feed Claude this instruction alongside the schema above:

```
Convert the following quest spec to YAML using the schema in QUEST_YAML_IMPORT.md.
Rules:
- Every field must be present. Use null for unused fields, never omit them.
- Use the | block scalar for all body text.
- All scene references use key strings only — no nesting.
- Do not add quotation marks to arrival_flavor or body text unless the player is speaking.
- Preserve all paragraph breaks in body text as blank lines between paragraphs.
- Each paragraph in body text must be a single continuous line — never hard-wrap at a column width. If the source spec has prose wrapped at 80 characters, unwrap each paragraph into one line before writing it to the body block.
- combat_encounter block only appears on scenes with scene_type: combat.
- choices: [] on combat scenes.
```
