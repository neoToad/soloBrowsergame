# Developer Documentation for soloBrowserGame

This document provides project-specific details for advanced developers working on this Django-based text RPG.

## Build/Configuration Instructions

### Prerequisites
- Python 3.10+
- Django 6.0+

### Local Setup
1. **Migrations**: Ensure the database is up to date:
   ```powershell
   python manage.py migrate
   ```
2. **Static Files**: The project uses static CSS for styling. Ensure they are collected or available in `static/`:
   ```powershell
   python manage.py collectstatic --noinput
   ```
3. **Fixtures**: The game relies on JSON fixtures for world data (scenes, choices, quests).
   - `game/fixtures/hub.json`: Contains the main hub areas (Square, Tavern, Notice Board).
   - `game/fixtures/quest_haunted_mine.json`: Contains the first playable quest.
   Load them into your local DB:
   ```powershell
   python manage.py loaddata game/fixtures/hub.json game/fixtures/quest_haunted_mine.json
   ```

## Testing Information

### Running Tests
Run all tests using the standard Django test runner:
```powershell
python manage.py test
```

### Writing New Tests
- **Fixtures**: Most tests require loading both `hub.json` and `quest_haunted_mine.json` because choices often link between them.
- **HTMX Testing**: The game uses HTMX for partial page updates. To test these views, include the `HTTP_HX_REQUEST='true'` header in your client requests.
  ```python
  response = self.client.post(reverse('start_quest', args=['my_quest']), HTTP_HX_REQUEST='true')
  ```
- **Session State**: The `game_session_id` is stored in `request.session`. Always initialize a session (e.g., by visiting `/game/`) before testing gameplay mechanics.

### Demo Test Case
The following is a simple test case demonstrating how to check scene navigation:
```python
from django.test import TestCase, Client
from django.urls import reverse

class DemoTest(TestCase):
    fixtures = ['game/fixtures/hub.json', 'game/fixtures/quest_haunted_mine.json']

    def test_hub_access(self):
        client = Client()
        # 1. Initialize session
        client.get('/game/')
        # 2. Check scene content
        response = client.get(reverse('scene_detail', kwargs={'scene_key': 'hub__main_square'}))
        self.assertContains(response, "Main Square")
        self.assertContains(response, "Check the notice board")
```

## Additional Development Information

### Code Style & Architecture
- **Django Standards**: Follow PEP 8 and Django's coding style (4-space indentation, clear variable names).
- **Scene/Choice System**: 
    - `Scene`: Represents a location or event. Can have `requires_roll` for skill checks.
    - `Choice`: Links Scenes. Can have `success_scene` and `failure_scene` for rolls.
    - `Quest`: A collection of scenes. The `Notice Board` dynamically renders quests based on `is_unlocked`, `required_quest`, and `required_stat` fields.
- **HTMX Integration**: Views return partial HTML strings when an HTMX request is detected. See `game/views.py` for how `render_to_string` is used to combine `scene_panel`, `stats_bar`, and `event_log`.
- **Stat Modifiers**: Use `game.utils.stat_modifier` for D&D-style modifiers: `(stat - 10) // 2`.
