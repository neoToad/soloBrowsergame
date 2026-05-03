# Quest Tracking (Text Mirror)

Source: quest_tracking.xlsx
Generated for diff-friendly reviews. Update this file when the spreadsheet changes.

## Quests

| Key | Title | Arc | Arc Order | Hub | Repeatable | Status | Unlock Requirements | Endings | Leads To | Notes | Ending Scene Keys |
|---|---|---|---|---|---|---|---|---|---|---|---|
| the-call | The Call | intro | 1 | hub__apartment | No | Complete | None | victory (x2)\ndefeat | the-morris-job | Introduces Vickie and Terrell. Two victory paths: talked out or fought. | victory: the-call__done-clean\nvictory: the-call__done-rough\ndefeat: the-call__beaten |
| the-morris-job | The Morris Job | intro | 2 | hub__apartment | No | Complete | the-call (any ending) | victory\nneutral (x2) | corkys | Introduces Morris and Dutch's operation. First courier job. Morris gained at entrance scene. | victory: the-morris-job__clean-delivery\nneutral: the-morris-job__clocked\nneutral: the-morris-job__hot-delivery |
| corkys | Corky's | intro | 3 | hub__apartment | No | Complete | the-morris-job (any ending) | victory\nneutral\ndefeat | the-ride | Introduces Sal. Moral weight: player pressures a civilian. Three approach paths to Sal. | victory: corkys__done-dealers-in\nneutral: corkys__done-sal-caved\ndefeat: corkys__done-sal-holds |
| the-ride | The Ride | intro | 4 | hub__apartment | No | Complete | corkys (any ending) | victory (x2)\ndefeat | TBD | Introduces Darius. Key choice: report to Dutch or stay quiet. Opens Kings cold-war thread. | victory: the-ride__done-straight\nvictory: the-ride__done-covered\ndefeat: the-ride__done-lost |

## Rewards

Totals account for all arrival changes across intermediate and ending scenes on each path.

| Quest Key | Ending | Cash | Rep | Heat | Items | Contacts | Gang Standing |
|---|---|---|---|---|---|---|---|
| the-call | victory (talked out) | 0 | +15 | 0 | — | sister | — |
| the-call | victory (fought) | +150 | +10 | +10 | brass_knuckles, zonk_smoked | sister | — |
| the-call | defeat | -25 | -5 | +10 | zonk_smoked | — | — |
| the-morris-job | victory | +200 | +15 | 0 | switchblade, zonk_smoked | morris | harlan-street-crew +10 |
| the-morris-job | neutral (clocked) | +175 | +8 | +8 | zonk_smoked | morris | harlan-street-crew +5 |
| the-morris-job | neutral (hot delivery) | +150 | +5 | +15 | zonk_smoked | morris | harlan-street-crew +3 |
| corkys | victory (intimidated path) | +200 | +10 | +5 | — | — | — |
| corkys | victory (leveraged path) | +200 | +10 | +3 | — | — | — |
| corkys | neutral | +100 | 0 | 0 | — | — | — |
| corkys | defeat | 0 | -5 | 0 | — | — | — |
| the-ride | victory (straight) | +350 | +15 | 0 | — | — | — |
| the-ride | victory (covered) | +300 | +10 | +5 | — | — | — |
| the-ride | defeat | 0 | -20 | +10 | — | — | — |

## Flags

| Flag Name | Set By Quest | Set By Choice/Ending | Description | Used By |
|---|---|---|---|---|
| the_call_talked_out | the-call | the-call__done-clean (hub return) | Player resolved Terrell without combat | Future gating TBD |
| the_call_fought_out | the-call | the-call__done-rough (hub return) | Player fought and won against Terrell | Future gating TBD |
| the_call_lost | the-call | the-call__beaten (hub return) | Player lost the fight with Terrell | Future gating TBD |
| morris_job_clean | the-morris-job | the-morris-job__clean-delivery (hub return) | Clean delivery, no police contact | Future gating TBD |
| morris_job_hot | the-morris-job | the-morris-job__hot-delivery or __clocked (hub return) | Delivery logged by Blues — both neutral endings | Future gating TBD |
| corkys_dealers_in | corkys | corkys__done-dealers-in (hub return) | Dealers back in — victory ending | Future gating TBD |
| corkys_sal_holds | corkys | corkys__done-sal-holds (hub return) | Counter-offer built, Dutch rejected it — defeat ending | Future gating TBD |
| corkys_sal_caved | corkys | corkys__done-sal-caved (hub return) | Sal held firm, Dutch handled it — neutral ending | Future gating TBD |
| corkys_read_room | corkys | corkys__read-the-room (approach choice) | Player took time to observe the bar — gates leverage choice | corkys__sal-face-to-face (leverage option) |
| the_ride_straight | the-ride | the-ride__done-straight (hub return) | Told Morris everything about Darius | Future gating TBD |
| the_ride_covered | the-ride | the-ride__done-covered (hub return) | Kept Darius quiet | Future gating TBD |
| the_ride_lost | the-ride | the-ride__done-lost (hub return) | Package lost — Dutch owed a debt in work | Future gating TBD |

## Dependencies

| Quest Key | Depends On Quest | Requirement Type | Details |
|---|---|---|---|
| the-morris-job | the-call | quest_completed | Any ending |
| corkys | the-morris-job | quest_completed | Any ending |
| the-ride | corkys | quest_completed | Any ending |

## Content Status

| Quest Key | Writing | YAML | Imported | Tested | Notes |
|---|---|---|---|---|---|
| the-call | Complete | Complete | Pending | Pending | |
| the-morris-job | Complete | Complete | Pending | Pending | |
| corkys | Complete | Complete | Pending | Pending | |
| the-ride | Complete | Complete | Pending | Pending | |

## World Impact

| Quest Key | Affects | Change Type | Description |
|---|---|---|---|
| the-call | Vickie (sister) | Contact gained | Sister gained on both victory paths |
| the-call | Terrell | Character introduced | Low-level enforcer — may recur |
| the-call | Westside Kings | Faction awareness | Player acts on Kings-adjacent turf for first time |
| the-morris-job | Morris | Contact gained | Morris gained at quest entrance (first scene arrival) |
| the-morris-job | Dutch | Reputation established | Dutch learns player's name on clean victory; monitors player on neutral paths |
| the-morris-job | Harlan Street Crew | Standing | +10 victory, +5 clocked, +3 hot delivery |
| corkys | Sal | Character introduced | Sal introduced — potential future hub owner depending on arc resolution |
| corkys | Corky's | Location status | Dealers back in (victory/neutral) or Dutch handles it after player fails (defeat) |
| corkys | Dutch | Reputation | Victory builds standing; defeat signals player's limits to Morris |
| the-ride | Darius | Character introduced | Operator working independently of his crew — recurring thread |
| the-ride | Dutch / Morris | Information state | Straight: Dutch knows Darius's name and message. Covered: he doesn't. |
| the-ride | Westside Kings | Tension raised | Darius operating without sanction — first visible fracture in BSB/Kings boundary |