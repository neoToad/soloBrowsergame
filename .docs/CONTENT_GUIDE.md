# Content Guide

## Setting and Tone

This is a noir crime game. The player starts as nobody and claws their way up from Errand Boy to Boss.

**Voice**: Terse. Dry. Matter-of-fact about violence. No melodrama.
**Perspective**: Second person ("You step into the alley."), present tense.
**Register**: Street-level. Avoid fantasy language, high-minded prose, or modern slang.

### Good examples (from the codebase)
> "Word travels fast. You're moving up."
> "You've earned your stripes."
> "Nobody moves without your say-so."

### What to avoid
- Exclamation points (except in rare moments of high action)
- Explaining the obvious ("You decide to attack the enemy.")
- Purple prose ("The moonlight cascades over the cobblestones...")
- Passive voice for dramatic beats

---

## Scene Writing

### Structure
- **Title**: Short. Location or situation. ("Back Alley", "The Drop", "Interrogation Room")
- **Body**: 2–4 sentences setting the scene. Establish atmosphere, stakes, or tension. Don't narrate choices — those go in the Choice labels.

### Scene types and their tone

| Type     | Tone                                                     |
|----------|----------------------------------------------------------|
| `hub`    | Familiar, routine. The Square, the Tavern. Home base.    |
| `normal` | Situational. Can be tense, transactional, or quiet.      |
| `combat` | Short and punchy. Immediate physical danger.             |
| `ending` | Consequential. Victory should feel earned, defeat earned |

### Endings
- **Victory**: Acknowledge the win cleanly. Don't oversell it.
- **Defeat**: No pity. What happened, happened.
- **Neutral**: Ambiguous. Something was gained and lost. Player should feel the trade-off.

---

## Choice Writing

Choices are actions, not thoughts.

**Good**: "Bribe the guard."
**Good**: "Take the back route."
**Bad**: "Decide to try bribing the guard and see if it works."
**Bad**: "Think about using your cunning to outsmart them."

### Length
- 3–8 words ideal.
- Up to 15 words if the nuance matters.

### Gated choices
If a choice requires a stat, item, or completed quest — the requirement handles the gate. Do not reference the gate in the label ("Use lockpick [requires item]"). The label should read naturally for a player who qualifies.

### `arrival_flavor`
Short line logged to EventLog when this choice resolves. First person or second person, past tense.
- "You slipped through the gap before anyone noticed."
- "The guard takes the money without looking up."

Omit if the next scene's body already covers the transition.

---

## Item Writing

- **Name**: Concrete noun. ("Flask of Rotgut", "Brass Knuckles", "Forged Papers")
- **Description**: One sentence. What it is, not what it does mechanically. Let the flavour breathe.

---

## Event Log Entries

The event log is the game's running commentary. Entries should read like a pulp novel's stage directions.

- Short. One sentence, rarely two.
- Immediate. What just happened.
- No over-explanation of mechanics.

**Good**: "You rolled a 14 (+2 modifier) = 16 vs DC 12 — Success!"
**Good**: "+150 XP."
**Good**: "The guard takes the money without looking up."
**Bad**: "You have successfully completed the quest and earned experience points!"
