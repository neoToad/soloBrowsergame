# Quest Tracking (Text Mirror)

Source: quest_tracking.xlsx
Generated for diff-friendly reviews. Update this file when the spreadsheet changes.

## Quests

| Key | Title | Arc | Arc Order | Hub | Repeatable | Status | Unlock Requirements | Endings | Leads To | Notes | Ending Scene Keys |
|---|---|---|---|---|---|---|---|---|---|---|---|
| the-call | The Call | intro | 1 | hub__apartment | No | Complete | None | victory\ndefeat | first-word | Introduces Vickie. First combat (Terrell). Sets up family thread. | victory: the-call__done\ndefeat: the-call__beaten |
| first-word | First Word | intro | 2 | hub__apartment | No | Complete | the-call (any ending) | victory\nneutral\ndefeat | corkys | Introduces Morris. First contact with Dutch's network. Pruitt introduced — opens Kings thread. | victory: first-word__done-paid\nneutral: first-word__done-partial\ndefeat: first-word__done-burned |
| corkys | Corky's | intro | 3 | hub__apartment | No | Complete | first-word (any ending) | victory\nneutral\ndefeat | the-ride | Introduces Sal and Corky's. Moral weight: player pressures a civilian. Dutch/Morris relationship deepens. | victory: corkys__done-dealers-in\ndefeat: corkys__done-sal-holds\nneutral: corkys__done-sal-caved |
| the-ride | The Ride | intro | 4 | hub__apartment | No | Complete | corkys (any ending) | victory (x2)\ndefeat | TBD | Introduces Darius. Key choice: report to Dutch or keep quiet. Opens Kings cold-war thread. | victory: the-ride__done-straight\nvictory: the-ride__done-covered\ndefeat: the-ride__done-lost |

## Rewards

| Quest Key | Ending | Cash | Rep | Heat | Items | Contacts | Properties |
|---|---|---|---|---|---|---|---|
| the-call | victory | 150 | 10 | 0 | brass_knuckles | sister |  |
| the-call | defeat | -25 | -5 | 10 |  |  |  |
| first-word | victory | 700 | 15 | 0 |  | morris |  |
| first-word | neutral | 350 | 5 | 0 |  | morris |  |
| first-word | defeat | 0 | -10 | 5 |  | morris |  |
| corkys | victory | 200 | 10 | 0 |  |  |  |
| corkys | defeat | 0 | -5 | 0 |  |  |  |
| corkys | neutral | 100 | 0 | 0 |  |  |  |
| the-ride | victory (straight) | 350 | 15 | 0 |  |  |  |
| the-ride | victory (covered) | 300 | 10 | 5 |  |  |  |
| the-ride | defeat | 0 | -20 | 10 |  |  |  |

## Flags

| Flag Name | Set By Quest | Set By Choice/Ending | Description | Used By |
|---|---|---|---|---|
| the_call_talked_out | the-call | the-call__squeeze (success choice) | Player resolved Terrell without combat | first-word (entrance choice gate) |
| the_call_fought_out | the-call | the-call__terrell (fight choice) | Player chose to fight Terrell | first-word (entrance choice gate) |
| the_call_lost | the-call | the-call__beaten (hub return) | Player lost the fight with Terrell | first-word (entrance choice gate) |
| first_word_paid_in_full | first-word | first-word__done-paid (hub return) | Full collection — victory ending | Future gating TBD |
| first_word_partial | first-word | first-word__done-partial (hub return) | Partial collection — neutral ending | Future gating TBD |
| first_word_burned | first-word | first-word__done-burned (hub return) | Nothing collected — defeat ending | Future gating TBD |
| corkys_dealers_in | corkys | corkys__done-dealers-in (hub return) | Dealers back in — victory ending | Future gating TBD |
| corkys_sal_holds | corkys | corkys__done-sal-holds (hub return) | Sal held out — defeat ending | Future gating TBD |
| corkys_sal_caved | corkys | corkys__done-sal-caved (hub return) | Dutch handled it — neutral ending | Future gating TBD |
| corkys_read_room | corkys | corkys__read-the-room (approach choice) | Player took time to read the bar — gates leverage choice | corkys__sal-face-to-face (leverage choice) |
| the_ride_straight | the-ride | the-ride__done-straight (hub return) | Told Morris everything about Darius — victory | Future gating TBD |
| the_ride_covered | the-ride | the-ride__done-covered (hub return) | Kept Darius quiet — victory | Future gating TBD |
| the_ride_lost | the-ride | the-ride__done-lost (hub return) | Package lost — defeat | Future gating TBD |

## Dependencies

| Quest Key | Depends On Quest | Requirement Type | Details |
|---|---|---|---|
| first-word | the-call | quest_completed | Any ending |
| corkys | first-word | quest_completed | Any ending |
| the-ride | corkys | quest_completed | Any ending |

## Content Status

| Quest Key | Writing | YAML | Imported | Tested | Notes |
|---|---|---|---|---|---|
| the-call | Complete | Complete | Pending | Pending | Original quest — not yet prose-reviewed |
| first-word | Complete | Complete | Pending | Pending | Original quest — not yet prose-reviewed |
| corkys | Complete | Complete | Pending | Pending | Prose rewritten per content guide |
| the-ride | Complete | Complete | Pending | Pending | Prose rewritten per content guide |

## World Impact

| Quest Key | Affects | Change Type | Description |
|---|---|---|---|
| the-call | Vickie (sister) | Contact gained | Player gains sister contact on victory path |
| the-call | Terrell | Character introduced | Low-level Kings enforcer — may recur |
| the-call | Westside Kings | Faction awareness | Player action on Kings turf for first time |
| first-word | Morris | Contact gained | Morris unlocked on all endings as Dutch's logistics contact |
| first-word | Pruitt / Westside Kings | Character introduced | Pruitt introduced — opens Kings relationship thread |
| first-word | Dutch | Reputation established | Dutch learns player's name on victory path |
| corkys | Sal | Character introduced | Sal introduced — future hub owner depending on arc resolution |
| corkys | Corky's | Location status | Dealers back in (victory/neutral) or Sal holds (defeat) |
| corkys | Dutch | Reputation | Victory builds standing; defeat signals unreliability |
| the-ride | Darius | Character introduced | Backstreet Boys operator — recurring antagonist/ally |
| the-ride | Dutch / Morris | Information state | Victory (straight): Dutch knows Darius's name. Victory (covered): he doesn't. |
| the-ride | Westside Kings cold war | Tension raised | Darius operating independently — signals fracture in BSB/Kings boundary |

