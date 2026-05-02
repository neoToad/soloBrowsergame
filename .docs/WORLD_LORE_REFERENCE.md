# World Lore Reference

Canonical reference sections extracted from `WORLD_LORE.md`.

## Hub Scenes

Hub scenes are permanent, reusable locations the player returns to between quests. Their body text must be true on the first visit and the fiftieth — no story-specific narration, no time-sensitive references.

---

### `hub__apartment`
**Location:** The Flats
**Title:** The Apartment
**Body text (reference):**
> Home. Relative term. The radiator clanks. The window looks out on a brick wall. There's a corkboard on the back of the door where you've started pinning job leads. Old habits die. New ones move in.

**Function:** Primary hub for the early game. Quest board is the corkboard. The notice board posts jobs from Dutch's network, family obligations, and street-level opportunities.

**Texture:** Water stain on the ceiling shaped like a boot. Radiator with opinions. The window has a view of a blank wall and you've started to find it calming, which is either personal growth or a bad sign.

---

### `hub__corkys`
**Location:** The Flats, two blocks from Reyes Boxing
**Title:** Corky's
**Body text (reference):**
> Sal's behind the bar, same as always. The two old men in the corner have been nursing pints since before you were born. The TV above the register shows a game nobody's watching. Corky's is the kind of bar that exists because bars like this need to exist.

**Function:** Mid-game hub once the player has established a working relationship with Sal. Quest board takes the form of regulars passing word, Sal quietly mentioning who's been asking around.

**Texture:** Photo behind the register of Sal and Dennis, both grinning, the bar looking exactly the same in the background. Pool table with a level problem that everybody knows about and accounts for. The jukebox works but only plays one era of music and nobody has worked out why.

**Note:** Corky's begins as a quest location (Dutch vs. Sal pressure job) before becoming a hub. It should not appear as a hub scene until that quest arc resolves. The transition is a world state, not a quest-level flag.

---

### `hub__reyes_boxing`
**Location:** The Flats
**Title:** Reyes Boxing
**Body text (reference):**
> Old equipment, fanatically maintained. The floors are clean. Everything else is held together with cable ties and goodwill. Eddie's somewhere in the building. He always is.

**Function:** Late-game or optional hub. Eddie doesn't post jobs — he points people in directions, once, quietly. The "notice board" here is a conversation with Eddie. Limited availability, high signal-to-noise.

**Texture:** Smell of canvas and old sweat that never fully leaves the air. Handwritten training schedules on a corkboard that has been there so long it's part of the wall. One heavy bag that is better than all the others and everyone knows not to claim it.

---

### `hub__the_strip_corner`
**Location:** The Strip
**Title:** The Corner
**Body text (reference):**
> High foot traffic, nobody looking at anybody else. The noodle place on the corner does a lunch special that runs out by noon. The dry cleaner next to it has been closed for renovation for fourteen months. The corner works because everyone's got somewhere else to be.

**Function:** Unlocked through Backstreet Boys or Westside Kings faction work. Street-level jobs, information brokering, mid-tier opportunities. The notice board is whoever's working the corner that day.

**Texture:** The bus stop nobody uses as a bus stop. A parking meter that's been out of service so long it's become a landmark. You can see three blocks in every direction, which is the whole point.

---
## Civilians & Locations

### Sal
**Type:** Civilian, bar owner
**Location:** Corky's, The Flats
**Deal:** Sal inherited Corky's from a friend who left town and just wants to run a quiet bar. Local guy, knows the neighborhood, not angling for anything. Dutch's dealers have been using Corky's as a sales floor for years — high foot traffic, habit as much as strategy. Sal wants them out. Dutch can't be seen backing down. The player gets hired by Dutch to apply pressure on Sal.
**Quest hook:** The player starts on the wrong side of this — pressuring a scared regular guy who just wants to run his bar. The longer they interact with Sal the more uncomfortable the moral math gets.
**Character:** Tired. Not defeated — tired. There's a difference. He's been running a dead friend's bar for four years and it's not working and he's going to keep doing it anyway, because what else is there. Funny in the way that stubborn people are funny — the specificity of his grievance, the dignity he maintains while someone is telling him his bar is not, in fact, his bar.

---

### Vickie
**Relation:** Player's sister
**Contact key:** `sister`
**Deal:** Sleazy, always getting into trouble. Wants to live a life where she can do Zonk and not much else. Calls the player only when she needs something. Genuinely loves them in her way and has absolutely no idea how much trouble she causes — or she knows and doesn't care. A chaos agent, not a victim. The player isn't protecting someone innocent, they're managing someone who will immediately create the next problem the second the current one is solved.
**Zonk use:** Heavy. Dedicated.
**Character:** Always completely confident. Has a completely coherent internal logic that simply does not account for consequences in the way that most people's internal logic does. The comedy of Vickie is that she is never wrong, as far as she's concerned. The tragedy of Vickie is the same thing.

---

### Councilor Linda Marsh
**Type:** City councilor, legitimate power
**Contact key:** `linda_marsh`
**Represents:** The Flats and the border of The New Build — publicly the voice of community preservation while quietly taking money from the developers eating her district alive.
**Public persona:** Tireless community advocate. Anti-crime, anti-drug, very visible at neighborhood cleanups. Has a newsletter with a recipe section. Owns a rescue dog named Biscuit. Posts about it constantly.
**Actual deal:** Frank Cahill uses her for planning permissions, zoning decisions, and the occasional quiet burial of an investigation. She tells herself she's managing a difficult situation. She's been telling herself that for eleven years.
**Also taking money from:** Craig Richards, who thinks it means something. It doesn't. Frank knows and finds it mildly amusing.
**Zonk:** Pills, slow release. Takes them like vitamins. Has completely reframed it in her own mind as a medical necessity. Does not consider herself a user.
**Character note:** Not evil — just been making one small reasonable decision at a time for over a decade and can't see the shape of what she's built anymore.
**Location:** District office, The Flats. Constituent services, newsletter production, Biscuit usually present. Smells like printer ink and someone's lunch. Where Frank Cahill's requests get processed without anyone writing anything down.

---

### Eddie Reyes
**Type:** Civilian, neutral party
**Contact key:** `eddie_reyes`
**Location:** Reyes Boxing, The Flats — two blocks from Corky's
**Deal:** Been running the gym for thirty years. Never fought professionally — had the talent, didn't have the patience for the politics. Trained people who went on to be successful fighters, prisoners, and corpses. Doesn't rank them differently.
**The gym:** Old equipment, fanatically maintained. Floors are clean. Everything else is falling apart.
**His specific quality:** Listens more than he talks. The only person in Creston who has told Dutch, Frank Cahill, and Richie Bucco something they didn't want to hear and had all three thank him afterward. Nobody brings their business through his door. It's been broken twice in thirty years. Eddie handled it himself both times. Nobody has tried a third time.
**His role:** Not a traditional contact — doesn't broker deals or pass information. But he knows everyone, everyone trusts him, and occasionally points someone in a direction. Quietly. Once. Doesn't follow up.
**Zonk:** Doesn't touch it. Has buried too many kids who did. The one topic that cracks his composure.

---
## Other Locations

### Bucco & Sons Imports
**Key:** `loc__bucco_imports`
**Neighborhood:** The Hill
**Front for:** The Bucco Family
**Surface:** Legitimate fine olive oil import business. Storefront showroom, tasting notes printed on thick card stock, a logo that a real designer made. The olive oil is genuinely excellent.
**Back of house:** Richie's office. Dark wood, a desk that's older than everyone in the room, a painting of a coastline that is definitely somewhere in Italy. Meetings happen here that do not appear in any calendar.

---

### The Dockside Warehouse
**Key:** `loc__docks_warehouse`
**Neighborhood:** The Docks
**Controlled by:** Bucco Family
**Function:** Primary smuggling throughput. Union workers who have been there long enough to know exactly what questions not to ask. The shipping containers move in and out on a schedule that looks like a legitimate import operation because it mostly is — with additions.
**Texture:** Forklifts, saltwater smell, the sound of the water under the dock, security that's light on the surface and heavy below it.

---
## Contacts

Contacts the player can acquire. Each has a `key` for use in `SceneContact` records.

| key | Name | Description |
|-----|------|-------------|
| `sister` | Vickie | Player's sister. Chaos agent. Available after The Call. Calls when she needs something, which is always. |
| `morris` | Morris | Dutch's logistics man. Unlocks Dutch-aligned job pipeline. |
| `dutch` | Dutch | Runs the Harlan Street Crew. Direct contact means you've cleared through Morris and arrived somewhere the crew takes seriously. |
| `sal` | Sal | Owner of Corky's. Acquired through the Corky's arc, depending on resolution. |
| `eddie_reyes` | Eddie Reyes | Gym owner. Rare, high-trust contact. Points in directions once. |
| `pruitt` | DeShawn Pruitt | Westside Kings council member. Opens Kings-side jobs. |
| `kings_contact` | Kings Contact | Generic Kings pipeline contact. Useful as long as the internal politics hold. |
| `darius` | Darius | Backstreet Boys-adjacent operator. Useful for Strip work. Complicated. |
| `craig_richards` | Craig Richards | Backstreet Boys leader. Insists on being called King. Opens BSB-side jobs. Low prestige, unpredictable. |
| `richie_bucco` | Richie Bucco | Bucco Family head. High-tier, high-risk. Not a contact you acquire casually or quickly. |
| `linda_marsh` | Councilor Marsh | Political access, slow burn, high risk. |
| `frank_cahill` | Lt. Cahill | Blues access. Not a contact you want. Or maybe you do. |

---
## Items

Items the player can carry. Each has a `key` for use in `SceneItem` records and requirements. Passive bonuses are applied via `get_effective_stats()` while the item is in inventory — they do not persist to the DB.

### Weapons

All weapons grant a passive `strength` bonus while carried.

| key | Name | Description | Passive Bonus |
|-----|------|-------------|---------------|
| `brass_knuckles` | Brass Knuckles | Someone else's initials scratched into the base. | +2 strength |
| `pipe` | Length of Pipe | Galvanized. Repurposed from something structural. | +2 strength |
| `switchblade` | Switchblade | Spring-loaded, matte handle. Works first time every time. | +3 strength |
| `crowbar` | Crowbar | Makes argument in a language everyone understands. | +3 strength |
| `9mm` | 9mm | Clean. Registered to someone who reported it lost. | +5 strength |
| `burner_pistol` | Burner Pistol | Unregistered. Has history you don't know about and don't want to. | +6 strength |

### Tools & Gear

No mechanical effect unless noted. Presence in inventory gates choices via `has_item` requirements.

| key | Name | Description | Passive Bonus |
|-----|------|-------------|---------------|
| `lockpick_set` | Lockpick Set | The good kind, not the tourist kind. | — |
| `bolt_cutters` | Bolt Cutters | The big ones. For serious locks or light panic. | — |
| `zip_ties` | Zip Ties | A handful. Multi-use. | — |
| `burner_phone` | Burner Phone | Fresh SIM. Untraceable for now. | — |
| `duct_tape` | Duct Tape | Utility. Appears in improvised solutions. | — |
| `police_scanner` | Police Scanner | Old model, still works, picks up most of what you need. | -3 heat |

### Drugs & Consumables

All consumables are removed from inventory on use (`is_consumable: true`).

| key | Name | Description | Effect |
|-----|------|-------------|--------|
| `zonk_pill` | Zonk (pill) | Slow release. Hallucinogenic edge. Harder to dose. | Restores 15 HP |
| `zonk_smoked` | Zonk (smoked) | The standard. Mellow, dissociative. | Restores 10 HP |

### Documents & MacGuffins

No effects. Exist only to satisfy `has_item` requirements.

| key | Name | Description |
|-----|------|-------------|
| `package_sealed` | Sealed Package | You don't know what's in it. That's the job. |
| `ledger` | Ledger | Handwritten. Names, numbers, dates. Belongs to someone who wants it back. |
| `envelope_cash` | Envelope of Cash | Unmarked bills, rubber-banded. |
| `flash_drive` | Flash Drive | Small, cheap, contents unknown. |
| `photo` | Photograph | Someone who would rather not be photographed doing what they're doing. |
| `key_storage` | Storage Unit Key | A key. Number stamped on the fob. |

---
## Enemies

Enemy entries for use in `CombatEncounter` records. Each has a `key`.

### Street-Level

| key | Name | Faction | Notes |
|-----|------|---------|-------|
| `terrell` | Terrell | Westside Kings (loose) | Solo. Young, reach but no discipline. Introduced in The Call. Threat lands through casualness, not volume; he says hard things like they cost him nothing. He is not a hothead. |
| `street_thug` | Street Thug | Unaffiliated | Generic low-level. Fast, undisciplined. Solo encounter. |
| `street_thug_x2` | Two Street Thugs | Unaffiliated | Group encounter. Coordinate loosely. |
| `street_thug_x3` | Three Street Thugs | Unaffiliated | Group encounter. First one is a distraction. |
| `corner_boy` | Corner Boy | Kings / BSB | Low-tier, more committed than a generic thug. Has something to prove. |

### Harlan Street Crew

| key | Name | Notes |
|-----|------|-------|
| `harlan_enforcer` | Harlan Enforcer | Mid-tier. Professional. Doesn't get creative, doesn't make mistakes. |
| `harlan_muscle_x2` | Two Harlan Muscle | Pair. One talks, one doesn't. The one who doesn't is the problem. |

### Westside Kings

| key | Name | Notes |
|-----|------|-------|
| `kings_soldier` | Kings Soldier | Mid-tier. Territorial. Fights like someone who grew up fighting. |
| `kings_enforcer` | Kings Enforcer | Senior muscle. Deliberate. Slower than a soldier but reads the room. |
| `pruitt_crew` | Pruitt's Crew | Group encounter. Loyalists. Fight together. Won't run unless Pruitt's out. |

### Backstreet Boys

| key | Name | Notes |
|-----|------|-------|
| `bsb_soldier` | BSB Soldier | Punches up in self-image. Punches at or below weight in practice. Flash. |
| `darius` | Darius | Named enemy. Competent. Loses because he misjudged the situation, not because he's weak. Dangerous in a rematch. |
| `craig_security` | Craig's Security | Professional hired help, not crew. Impersonal. More effective than BSB regulars. |

### Bucco Family

| key | Name | Notes |
|-----|------|-------|
| `bucco_associate` | Bucco Associate | Older, methodical. Doesn't want to fight. Will finish one. |
| `bucco_muscle` | Bucco Muscle | Hired. Large. The kind of large that comes with a suit. Very little expression. |
| `dockworker_hostile` | Hostile Dockworker | Not mob, but mob-adjacent. Union solidarity takes interesting forms at the Docks. |

### The Blues

| key | Name | Notes |
|-----|------|-------|
| `blues_officer` | Blues Officer | Combat with a Blues officer is a serious escalation. Heat cost significant. Not a casual encounter. |
| `cahill_detail` | Cahill's Detail | Two plainclothes officers. Professional. Arrives without announcement. |

### Named / Special

| key | Name | Notes |
|-----|------|-------|
| `big_mal` | Big Mal | Independent heavy. For hire. Shows up when someone wants to send a message they're paying for. No faction loyalty. |
| `the_cook` | The Cook | Zonk cook. Defensive encounter only — he didn't want this. Better with improvised weapons than anyone expects. |

---
