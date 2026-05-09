# Solo Browser Game

A turn-based, single-player browser RPG built with Django and HTMX. The player navigates a branching narrative — making choices, fighting enemies, managing stats — with no page reloads. The server renders everything; JavaScript is minimal and purposeful.

**Live:** _[URL placeholder]_
**Code:** _[GitHub placeholder]_

---

## Stack

- **Python / Django** — all game logic, data modelling, and template rendering
- **HTMX** — partial HTML swaps for interactive UI without a JavaScript framework
- **SQLite** — simple persistence; the game is single-player by design
- **Custom admin tool** — a Django-based quest builder (canvas editor, scene/choice CRUD, requirement authoring)

---

## Architectural decisions

### Services layer

The project uses a deliberate separation between views, services, and models. Views load session state and call into services; services contain all game logic and return data (strings, dataclasses, dicts); models hold data and enforce invariants. Nothing crosses that boundary the other way.

The reason is practical: game logic gets called from multiple entry points. `process_arrival()` runs when the player picks a choice, when they win or lose a combat, and when a quest completes. If that logic lived in a view it would be copied or hard to reach. Keeping it in a service means callers just import and call it with the same interface.

The concrete boundary rule is: services return log strings; views create `EventLog` entries. This keeps services testable in isolation — they take plain Python arguments and return plain data, so a test can call them directly without a fake HTTP request or any Django middleware in the loop.

### Two-phase combat

Combat turns are split across two HTTP requests: one for the player's attack, one for the enemy's response.

When the player attacks, the service resolves the player's roll, applies damage, and then **immediately pre-rolls the enemy's counter-attack** and persists the result to `CombatState` (`pending_enemy_roll`, `pending_enemy_total`, `pending_enemy_hit`, `pending_enemy_damage`). The response renders the player's attack outcome and a "take the hit" button.

When the player clicks that button, the server reads the pre-rolled enemy attack from the database and applies it. Nothing is re-rolled; the outcome was already decided.

The reason for pre-rolling: if the enemy attack were rolled on the second request, a player could refresh or abandon the request to fish for a better result. Pre-rolling at commit time means the outcome is fixed the moment the player's turn ends — the follow-up request can only reveal it, not change it.

### Requirement and gating system

Every choice and scene can have attached `RequirementGroup` rows. Each group contains one or more `Requirement` conditions with internal AND or OR logic. Multiple groups on the same choice are always ANDed — every group must pass.

Conditions cover: stat thresholds, item presence or absence, quest completion, quest ending type, flags, contacts, level, and XP. Evaluating a requirement against the player's current state uses a registry pattern — each condition type registers an evaluator function via `@Requirement.register_evaluator`, and `Requirement.evaluate()` dispatches to it. Adding a new condition type means writing one function and one decorator line; nothing else changes.

The runtime evaluates requirements against a `PlayerContext` dataclass — a snapshot of stats, inventory, completed quests, and flags. This is constructed once per request and passed through the evaluation chain, avoiding repeated database reads.

### HTMX approach

The UI updates without full page reloads, but there is no JavaScript framework and no API layer. HTMX posts to Django views that return rendered HTML fragments — a new scene panel, an updated inventory list, a fresh event log entry — which HTMX swaps into the DOM.

The alternative would have been a REST API consumed by a frontend framework. That approach requires maintaining two codebases (or a monorepo with more moving parts), serializing game state to JSON, and writing client-side state management. Because the game's UI is naturally server-driven — the server always knows the canonical game state — returning HTML directly is both simpler and less error-prone. There is no risk of the client and server disagreeing about what the player's current scene is.

The tradeoff is that the server renders more on every interaction. For a single-player game with simple queries, this is not a meaningful cost.

---

## Project structure

```
game/
  models/         # split by domain: world, player, combat, items, property, requirements
  services/       # stateless business logic: arrival, combat, progression, scene, session
  services/gameplay/  # per-action handlers: resolve_choice, combat turns, use_item
  presentation/   # HTMX response helpers
  templates/      # Django templates, including HTMX partials
  tests/          # model, service, and fixture tests
```