# Jobs system spec

Jobs are replayable criminal work. Unlike quests, they have no fixed narrative — the same job can be run repeatedly with different outcomes depending on stats, choices, and accumulated flags. Every job has a cooldown measured in turns before it becomes available again.

---

## Entry points

There are two ways to start a job. Both are player-initiated — the world never delivers work to the player.

**Recon.** Each district hub scene contains job targets. The player cases a target by choosing to observe it. The observation text and resulting modifiers depend on the player's Cunning — everyone can case a place, sharper players see more. After reading the intel, the player chooses to commit or walk away. Walking away is free. The target remains caseable on the next visit.

**Contacts.** Contacts offer exclusive jobs not visible in any district. Each contact has their own interaction style — some approach you, some wait to be asked, some leave a note. Contacts hand over pre-cased intel, equivalent to high-tier recon regardless of the player's Cunning. The player commits or declines. Contacts have their own cooldown independent of the base job.

A target on cooldown remains visible in its scene but cannot be cased or started. The scene notes how long until it resets.

---

## Recon tiers

Every job has three recon tiers selected by the player's effective Cunning. Higher tiers reduce Beat 1 difficulty, unlock additional approach choices, and raise the payout ceiling.

| Tier | Min Cunning | Beat 1 difficulty | Extra approach | Payout ceiling |
|---|---|---|---|---|
| Low | 0 | Base | None | Base |
| Mid | 7 | −1 | One additional | +15% |
| High | 12 | −2 | Best approach | +35% |

Contact intel always applies high-tier modifiers.

---

## Beat structure

Every job runs four beats in order. Beats are linear with one branch point each.

**Beat 0 — recon.** No roll. The player reads their intel and commits or walks away. Skipped entirely when starting via a contact.

**Beat 1 — approach.** Stat check. The player chooses how to enter. Choice availability depends on recon tier. Difficulty is reduced by the recon modifier. The outcome sets a flag that determines which Beat 2 variant runs. A failed roll sets an additional flag that raises Beat 2 difficulty.

**Beat 2 — complication.** Stat check. Which variant runs is determined by the flag set in Beat 1. A job has as many Beat 2 variants as it has meaningful approach paths. Some beats allow aborting for a reduced payout rather than rolling.

**Beat 3 — resolution.** No roll. The job concludes. The fixer's voice appears here for the first time — not before. Payout, heat, and rep are applied. The job enters cooldown.

---

## Rewards

Rewards scale with run count. Cash and heat improve with familiarity; rep gains flatten after several runs — the neighbourhood stops being impressed.

| Run count | Cash | Heat | Rep |
|---|---|---|---|
| 0–2 | Base | Base | Base |
| 3–6 | +15–25% | −10% | +20% |
| 7+ | +30–45% | −20% | Base (routine) |

The final payout is the reward tier cash range multiplied by the recon payout modifier.

---

## Contacts

Contacts are always in the world. Some are visible from the start; better ones appear only after requirements are met — rank, completed quests, or job run milestones. A contact that hasn't been unlocked gives no indication it exists.

Each contact has three authored text states: a first-meeting introduction, a standard job offer, and a response for when they have nothing available this cycle. A contact with nothing to offer stays in their scene — they don't disappear.

Contacts gate their jobs by prior run count and flags in addition to their own unlock requirements. A contact can offer multiple jobs at different thresholds.

---

## Flags

Jobs use the existing flag system. Flags set during a job persist across cooldowns.

| Flag | When set |
|---|---|
| `approach_{path}` | Beat 1 — records which approach the player chose |
| `approach_{path}_failed` | Beat 1 — records a failed roll on a given approach |
| `ran_{job_slug}_{n}x` | On completion at milestones: 3, 5, 10 runs |
| `met_{contact_slug}` | On first interaction with a contact |

`ran_{job_slug}_{n}x` flags are the bridge to quests. Reaching a milestone can unlock a quest that acknowledges the player's pattern and escalates the stakes.

---

## Districts and job types

| District | Job types |
|---|---|
| Main square | Low-tier robbery |
| Garment district | Protection racket |
| The docks | Courier, debt collection |
| Uptown | High-tier robbery (rank-gated) |

---

## Designed templates

| Job | Stats used | Approach branch | Cooldown |
|---|---|---|---|
| Store robbery | Reflexes / Cunning / Nerve | Alley vs. front-door; recovery path on alley fail | 3 turns |
| Protection racket | Nerve / Charisma | Direct vs. friendly | 4 turns |
| Courier run | Reflexes / Cunning | Route A vs. route B | 3 turns |
| Debt collection | Strength / Nerve | Solo vs. bring backup | 5 turns |

---

## Initial contact roster

| Contact | Location | Style | Unlock | Jobs offered |
|---|---|---|---|---|
| Pawn shop owner | Main square | You ask | None | Mid-tier robbery |
| Carla the fence | Rusty Anchor | Pulls you aside | `ran_store_robbery_3x` | Bonded warehouse |
| Mickey Two-Fingers | Card room | Pulls you aside | Rank 2 | High-value protection |
| Court clerk | Garment district | Sends word | Quest flag | Bail bondsman jobs |
| Dock foreman | The docks | You ask | `ran_courier_3x` | Off-manifest heists |
