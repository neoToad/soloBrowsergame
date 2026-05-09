# Quest Tracking (Text Mirror)

Source: quest_tracking.xlsx
Generated for diff-friendly reviews. Update this file when the spreadsheet changes.

## Quests

| Key | Title | Arc | Arc Order | Hub | Repeatable | Status | Unlock Requirements | Endings | Leads To | Notes | Ending Scene Keys |
|---|---|---|---|---|---|---|---|---|---|---|---|
| the-boundary | The Boundary | -- | 0 | hub__westside_corner | No | Complete | None | victory<br>neutral<br>defeat | TBD | Someone's been running product two blocks into Kings territory from the Flats side. The council wants it stopped quietly. They're asking you. | victory: the-boundary__done<br>neutral: the-boundary__messy<br>defeat: the-boundary__burned |
| the-regular | The Regular | -- | 0 | hub__corkys | No | Complete | None | victory<br>neutral<br>defeat | TBD | Danny Kowalski hasn't been in for two weeks. Tuesday, Thursday, every week for eleven years, and then nothing. Sal's not asking you to do anything about it. He's just saying it. | victory: the-regular__done<br>neutral: the-regular__scared-off<br>defeat: the-regular__beaten |
| the-strip-job | The Strip Job | -- | 0 | hub__the_strip | No | Complete | None | victory<br>neutral<br>defeat | the-tab | There's an electronics shop two blocks down from the corner. You've walked past it three times this week without meaning to. Tonight feels like the night. | victory: the-strip-job__done<br>neutral: the-strip-job__complications<br>defeat: the-strip-job__burned |
| the-tab | The Tab | -- | 0 | hub__corkys | No | Complete | the-strip-job (any ending) | victory<br>neutral (x2)<br>defeat | TBD | A guy ran up a tab he couldn't cover and left a flash drive behind the bar. Now two different people are asking about him. Sal wants to know if he needs to worry. | victory: the-tab__clean<br>neutral: the-tab__blues<br>neutral: the-tab__buccos<br>defeat: the-tab__burned |
| the-tail | The Tail | -- | 0 | hub__the_strip | No | Complete | None | victory<br>neutral (x2)<br>defeat | the-witness | Burner number, no name. Someone's watching a Strip regular and the caller wants to know who hired them. Then they want them gone. | victory: the-tail__clean-exit<br>neutral: the-tail__loose-end<br>neutral: the-tail__messy-exit<br>defeat: the-tail__burned |
| the-witness | The Witness | -- | 0 | hub__westside_corner | No | Complete | the-tail (any ending) | victory<br>neutral (x2)<br>defeat | TBD | A Kings soldier named Calvin has been missing for four days. His crew thinks he's being leaned on. They want someone outside the Kings to find him before it becomes a loyalty quest... | neutral: the-witness__clean-return<br>neutral: the-witness__deon-knows<br>victory: the-witness__council<br>defeat: the-witness__sitting-on-it |
| the-call | The Call | intro | 1 | hub__apartment | No | Complete | None | victory (x2)<br>defeat | the-morris-job | Your sister reached out. First time in three years. She needs something taken care of. Family's family. | victory: the-call__done-clean<br>victory: the-call__done-rough<br>defeat: the-call__beaten |
| crossing-lines | Crossing Lines | intro | 2 | hub__apartment | No | Complete | the-morris-job (any ending) | victory | TBD | Morris has a delivery that touches more parts of the city than it should. That’s either a mistake or the point. | victory: crossing-lines__ending |
| the-morris-job | The Morris Job | intro | 2 | hub__apartment | No | Complete | the-call (any ending) | victory<br>neutral (x2) | corkys, crossing-lines | Someone called Morris has a package that needs moving across the Flats. Simple job. First one usually is. | victory: the-morris-job__clean-delivery<br>neutral: the-morris-job__hot-delivery<br>neutral: the-morris-job__clocked |
| corkys | Corky's | intro | 3 | hub__apartment | No | Complete | the-morris-job (any ending) | victory<br>neutral<br>defeat | the-ride | Dutch wants his dealers back in a bar called Corky's. The owner pushed back. You're the push. | victory: corkys__done-dealers-in<br>defeat: corkys__done-sal-holds<br>neutral: corkys__done-sal-caved |
| the-ride | The Ride | intro | 4 | hub__apartment | No | Complete | corkys (any ending) | victory (x2)<br>defeat | TBD | Morris has a courier job. Pick up a package, deliver it across the Flats. Simple work. It stops being simple at the handoff. | victory: the-ride__done-straight<br>victory: the-ride__done-covered<br>defeat: the-ride__done-lost |

## Rewards

| Quest Key | Ending | Cash | Rep | Heat | Items | Contacts | Gang Standing |
|---|---|---|---|---|---|---|---|
| the-boundary | TBD | -- | -- | -- | -- | -- | -- |
| the-regular | TBD | -- | -- | -- | -- | -- | -- |
| the-strip-job | TBD | -- | -- | -- | -- | -- | -- |
| the-tab | TBD | -- | -- | -- | -- | -- | -- |
| the-tail | TBD | -- | -- | -- | -- | -- | -- |
| the-witness | TBD | -- | -- | -- | -- | -- | -- |
| the-call | victory (talked out) | 0 | +15 | 0 | -- | sister | -- |
| the-call | victory (fought) | +150 | +10 | +10 | brass_knuckles, zonk_smoked | sister | -- |
| the-call | defeat | -25 | -5 | +10 | zonk_smoked | -- | -- |
| crossing-lines | TBD | -- | -- | -- | -- | -- | -- |
| the-morris-job | victory | +200 | +15 | 0 | switchblade, zonk_smoked | morris | harlan-street-crew +10 |
| the-morris-job | neutral (clocked) | +175 | +8 | +8 | zonk_smoked | morris | harlan-street-crew +5 |
| the-morris-job | neutral (hot delivery) | +150 | +5 | +15 | zonk_smoked | morris | harlan-street-crew +3 |
| corkys | victory (intimidated) | +200 | +10 | +5 | -- | -- | -- |
| corkys | victory (leveraged) | +200 | +10 | +3 | -- | -- | -- |
| corkys | neutral | +100 | 0 | 0 | -- | -- | -- |
| corkys | defeat | 0 | -5 | 0 | -- | -- | -- |
| the-ride | victory (straight) | +350 | +15 | 0 | -- | -- | -- |
| the-ride | victory (covered) | +300 | +10 | +5 | -- | -- | -- |
| the-ride | defeat | 0 | -20 | +10 | -- | -- | -- |

## Flags

| Flag Name | Set By Quest | Set By Choice/Ending | Description | Used By |
|---|---|---|---|---|
| corkys_read_room | corkys | corkys__read-the-room / Approach Sal | Flag set via choice in corkys__read-the-room | Future gating TBD |
| corkys_dealers_in | corkys | corkys__done-dealers-in / Back to the apartment | Flag set via choice in corkys__done-dealers-in | Future gating TBD |
| corkys_sal_holds | corkys | corkys__done-sal-holds / Back to the apartment | Flag set via choice in corkys__done-sal-holds | Future gating TBD |
| corkys_sal_caved | corkys | corkys__done-sal-caved / Back to the apartment | Flag set via choice in corkys__done-sal-caved | Future gating TBD |
| the_call_talked_out | the-call | the-call__done-clean / Back to the apartment | Flag set via choice in the-call__done-clean | Future gating TBD |
| the_call_fought_out | the-call | the-call__done-rough / Back to the apartment | Flag set via choice in the-call__done-rough | Future gating TBD |
| the_call_lost | the-call | the-call__beaten / Back to the apartment | Flag set via choice in the-call__beaten | Future gating TBD |
| morris_job_clean | the-morris-job | the-morris-job__clean-delivery / Back to the apartment | Flag set via choice in the-morris-job__clean-delivery | Future gating TBD |
| morris_job_hot | the-morris-job | the-morris-job__hot-delivery / Back to the apartment | Flag set via choice in the-morris-job__hot-delivery | Future gating TBD |
| morris_job_hot | the-morris-job | the-morris-job__clocked / Back to the apartment | Flag set via choice in the-morris-job__clocked | Future gating TBD |
| the_ride_straight | the-ride | the-ride__done-straight / Back to the apartment | Flag set via choice in the-ride__done-straight | Future gating TBD |
| the_ride_covered | the-ride | the-ride__done-covered / Back to the apartment | Flag set via choice in the-ride__done-covered | Future gating TBD |
| the_ride_lost | the-ride | the-ride__done-lost / Back to the apartment | Flag set via choice in the-ride__done-lost | Future gating TBD |
| strip_job_cased | the-strip-job | the-strip-job__the-corner / Watch it a while longer | Flag set via choice in the-strip-job__the-corner | Future gating TBD |
| strip_job_witness | the-strip-job | the-strip-job__the-back-room / Tell him to forget he saw you | Flag set via choice in the-strip-job__the-back-room | Future gating TBD |
| strip_job_witness | the-strip-job | the-strip-job__the-back-room / Take his phone first | Flag set via choice in the-strip-job__the-back-room | Future gating TBD |
| strip_job_witness_tied | the-strip-job | the-strip-job__the-back-room / Zip tie him to the shelf | Flag set via choice in the-strip-job__the-back-room | Future gating TBD |
| tail_watcher_tied | the-tail | the-tail__what-to-do / Zip tie him to the steering wheel and walk | Flag set via choice in the-tail__what-to-do | Future gating TBD |
| tail_watcher_loose | the-tail | the-tail__what-to-do / Tell him to drive and not come back | Flag set via choice in the-tail__what-to-do | Future gating TBD |
| witness_calvin_silent | the-witness | the-witness__the-decision / Tell Calvin to say he saw nothing, send him back clean | Flag set via choice in the-witness__the-decision | Future gating TBD |
| witness_deon_told | the-witness | the-witness__the-decision / Tell Deon exactly what Calvin saw | Flag set via choice in the-witness__the-decision | Future gating TBD |
| witness_council_told | the-witness | the-witness__the-decision / Take it to the Kings council directly | Flag set via choice in the-witness__the-decision | Future gating TBD |
| witness_held | the-witness | the-witness__the-decision / Keep the information yourself, send Calvin back with nothing | Flag set via choice in the-witness__the-decision | Future gating TBD |

## Dependencies

| Quest Key | Depends On Quest | Requirement Type | Details |
|---|---|---|---|
| corkys | the-morris-job | quest_completed | Any ending |
| crossing-lines | the-morris-job | quest_completed | Any ending |
| the-morris-job | the-call | quest_completed | Any ending |
| the-ride | corkys | quest_completed | Any ending |
| the-tab | the-strip-job | quest_completed | Any ending |
| the-witness | the-tail | quest_completed | Any ending |

## Content Status

| Quest Key | Writing | YAML | Imported | Tested | Notes |
|---|---|---|---|---|---|
| the-boundary | Complete | Complete | Pending | Pending | -- |
| the-regular | Complete | Complete | Pending | Pending | -- |
| the-strip-job | Complete | Complete | Pending | Pending | -- |
| the-tab | Complete | Complete | Pending | Pending | -- |
| the-tail | Complete | Complete | Pending | Pending | -- |
| the-witness | Complete | Complete | Pending | Pending | -- |
| the-call | Complete | Complete | Pending | Pending | -- |
| crossing-lines | Complete | Complete | Pending | Pending | -- |
| the-morris-job | Complete | Complete | Pending | Pending | -- |
| corkys | Complete | Complete | Pending | Pending | -- |
| the-ride | Complete | Complete | Pending | Pending | -- |

## World Impact

| Quest Key | Affects | Change Type | Description |
|---|---|---|---|
| the-boundary | TBD | TBD | Derived from YAML - pending narrative curation |
| the-regular | TBD | TBD | Derived from YAML - pending narrative curation |
| the-strip-job | TBD | TBD | Derived from YAML - pending narrative curation |
| the-tab | TBD | TBD | Derived from YAML - pending narrative curation |
| the-tail | TBD | TBD | Derived from YAML - pending narrative curation |
| the-witness | TBD | TBD | Derived from YAML - pending narrative curation |
| the-call | Vickie (sister) | Contact gained | Sister gained on both victory paths |
| the-call | Terrell | Character introduced | Low-level enforcer, may recur |
| the-call | Westside Kings | Faction awareness | Player acts on Kings-adjacent turf for first time |
| crossing-lines | TBD | TBD | Derived from YAML - pending narrative curation |
| the-morris-job | Morris | Contact gained | Morris gained at quest entrance (first scene arrival) |
| the-morris-job | Dutch | Reputation established | Dutch learns player's name on clean victory; monitors on neutral paths |
| the-morris-job | Harlan Street Crew | Standing | +10 victory, +5 clocked, +3 hot delivery |
| corkys | Sal | Character introduced | Sal introduced, potential future hub owner depending on arc resolution |
| corkys | Corky's | Location status | Dealers back in (victory/neutral) or Dutch handles it himself (defeat) |
| corkys | Dutch | Reputation | Victory builds standing; defeat signals player's limits to Morris |
| the-ride | Darius | Character introduced | Operator working independently of his crew, recurring thread |
| the-ride | Dutch / Morris | Information state | Straight: Dutch knows Darius's name and message. Covered: he doesn't. |
| the-ride | Westside Kings | Tension raised | Darius operating without sanction, first visible fracture in BSB/Kings boundary |
