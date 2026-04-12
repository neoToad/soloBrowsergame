from django.test import TestCase, Client
from django.urls import reverse
from .models import Scene, GameSession, PlayerStats, Choice, Quest, CompletedQuest

class GameNavigationTest(TestCase):
    fixtures = ['game/fixtures/hub.json', 'game/fixtures/quest_warehouse_job.json']

    def setUp(self):
        self.client = Client()

    def test_root_redirects_to_game(self):
        response = self.client.get('/')
        self.assertRedirects(response, '/game/', target_status_code=302)

    def test_game_hub_creates_session_and_redirects(self):
        response = self.client.get('/game/')
        self.assertRedirects(response, reverse('scene_detail', kwargs={'scene_key': 'hub__main_square'}))
        
        # Check if session was created in DB
        self.assertEqual(GameSession.objects.count(), 1)
        # Check if stats were created
        self.assertEqual(PlayerStats.objects.count(), 1)
        # Check if session ID is in request.session
        self.assertIn('game_session_id', self.client.session)

    def test_scene_navigation(self):
        # Initialize session
        self.client.get('/game/')
        
        # Go to notice board
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'hub__notice_board'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The Board")
        self.assertContains(response, "Head back outside")

    def test_stat_gated_choice(self):
        # Initialize session
        self.client.get('/game/')
        game_session = GameSession.objects.first()
        stats = game_session.stats
        
        # Warehouse Job entrance scene
        scene = Scene.objects.get(key='warehouse__loading_dock')
        
        # Choice 5: "Slip around back."
        choice_sneak = Choice.objects.get(pk=5)
        
        # Create a Requirement for agility 7
        from .models import Requirement, RequirementGroup
        req = Requirement.objects.create(
            condition_type='stat_gte',
            stat_name='agility',
            stat_value=7
        )
        group = RequirementGroup.objects.create(
            label='Agility 7 gate',
            logic='all'
        )
        group.requirements.add(req)
        choice_sneak.requirements.add(group)
        
        # Check that it's NOT visible with default agility (5)
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'warehouse__loading_dock'}))
        self.assertNotContains(response, "Slip around back.")
        
        # Increase agility to 7
        stats.agility = 7
        stats.save()
        
        # Check that it IS visible now
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'warehouse__loading_dock'}))
        self.assertContains(response, "Slip around back.")

    def test_persistent_session(self):
        # First visit
        self.client.get('/game/')
        session_id_1 = self.client.session['game_session_id']
        
        # Second visit
        self.client.get('/game/')
        session_id_2 = self.client.session['game_session_id']
        
        self.assertEqual(session_id_1, session_id_2)
        self.assertEqual(GameSession.objects.count(), 1)

    def test_htmx_choice_resolve(self):
        # Initialize session
        self.client.get('/game/')
        session = GameSession.objects.first()
        initial_scene = session.current_scene
        
        # Get a valid choice for the current scene (Main Square)
        # Choice 1 -> hub__notice_board (target_scene)
        choice = Choice.objects.filter(scene=initial_scene).first()
        
        response = self.client.post(
            reverse('choice_resolve', kwargs={'choice_id': choice.pk}),
            HTTP_HX_REQUEST='true'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="scene-panel"', response.content.decode())
        
        session.refresh_from_db()
        self.assertNotEqual(session.current_scene, initial_scene)
        # For non-roll choices, it uses target_scene
        self.assertEqual(session.current_scene, choice.target_scene)

class RequirementEvaluationTest(TestCase):
    def test_stat_gte(self):
        from types import SimpleNamespace
        from .models import Requirement, PlayerContext
        stats = SimpleNamespace(strength=10, level=5)
        ctx = PlayerContext(stats=stats, inventory={}, completed_map={})
        req = Requirement(condition_type='stat_gte', stat_name='strength', stat_value=10)
        self.assertTrue(req.evaluate(ctx))
        req.stat_value = 11
        self.assertFalse(req.evaluate(ctx))

    def test_has_item_missing_item(self):
        from .models import Requirement, PlayerContext
        req_has = Requirement(condition_type='has_item', required_item_id=1)
        req_missing = Requirement(condition_type='missing_item', required_item_id=1)
        
        inventory = {1: "some_item_instance"}
        ctx = PlayerContext(stats=None, inventory=inventory, completed_map={})
        self.assertTrue(req_has.evaluate(ctx))
        self.assertFalse(req_missing.evaluate(ctx))
        
        inventory = {2: "other_item"}
        ctx.inventory = inventory
        self.assertFalse(req_has.evaluate(ctx))
        self.assertTrue(req_missing.evaluate(ctx))

    def test_quest_completed_not_done(self):
        from .models import Requirement, PlayerContext
        req_done = Requirement(condition_type='quest_completed', required_quest_id=1)
        req_not_done = Requirement(condition_type='quest_not_done', required_quest_id=1)
        
        completed_map = {1: 'victory'}
        ctx = PlayerContext(stats=None, inventory={}, completed_map=completed_map)
        self.assertTrue(req_done.evaluate(ctx))
        self.assertFalse(req_not_done.evaluate(ctx))
        
        completed_map = {2: 'victory'}
        ctx.completed_map = completed_map
        self.assertFalse(req_done.evaluate(ctx))
        self.assertTrue(req_not_done.evaluate(ctx))

    def test_quest_ending(self):
        from .models import Requirement, PlayerContext
        req = Requirement(condition_type='quest_ending', required_quest_id=1, required_ending_type='victory')
        
        ctx = PlayerContext(stats=None, inventory={}, completed_map={1: 'victory'})
        self.assertTrue(req.evaluate(ctx))
        ctx.completed_map = {1: 'defeat'}
        self.assertFalse(req.evaluate(ctx))
        ctx.completed_map = {2: 'victory'}
        self.assertFalse(req.evaluate(ctx))

    def test_level_gte(self):
        from types import SimpleNamespace
        from .models import Requirement, PlayerContext
        stats = SimpleNamespace(level=5)
        ctx = PlayerContext(stats=stats, inventory={}, completed_map={})
        req = Requirement(condition_type='level_gte', stat_value=5)
        self.assertTrue(req.evaluate(ctx))
        req.stat_value = 6
        self.assertFalse(req.evaluate(ctx))

    def test_requirement_group_logic(self):
        from .models import Requirement, RequirementGroup, PlayerContext
        from unittest.mock import MagicMock
        
        # We need to save them to use ManyToMany requirements.all() or mock the queryset
        # RequirementGroup.evaluate uses self.requirements.all()
        
        r1 = Requirement.objects.create(condition_type='stat_gte', stat_name='strength', stat_value=10)
        r2 = Requirement.objects.create(condition_type='stat_gte', stat_name='agility', stat_value=10)
        
        group_all = RequirementGroup.objects.create(label='All', logic='all')
        group_all.requirements.add(r1, r2)
        
        group_any = RequirementGroup.objects.create(label='Any', logic='any')
        group_any.requirements.add(r1, r2)
        
        from types import SimpleNamespace
        stats_both = SimpleNamespace(strength=10, agility=10)
        stats_one = SimpleNamespace(strength=10, agility=5)
        stats_none = SimpleNamespace(strength=5, agility=5)
        
        self.assertTrue(group_all.evaluate(PlayerContext(stats_both, {}, {})))
        self.assertFalse(group_all.evaluate(PlayerContext(stats_one, {}, {})))
        
        self.assertTrue(group_any.evaluate(PlayerContext(stats_one, {}, {})))
        self.assertFalse(group_any.evaluate(PlayerContext(stats_none, {}, {})))
        
        # Empty group
        group_empty = RequirementGroup.objects.create(label='Empty', logic='all')
        self.assertTrue(group_empty.evaluate(PlayerContext(stats_none, {}, {})))

class CombatTest(TestCase):
    fixtures = ['game/fixtures/hub.json', 'game/fixtures/quest_warehouse_job.json', 'game/fixtures/quest_street_debt.json']

    def setUp(self):
        self.client = Client()
        self.client.get('/game/')
        # In case multiple sessions exist, get the last one created by our client
        from django.contrib.sessions.models import Session
        session_id = self.client.session.session_key
        self.session = GameSession.objects.get(session_key=session_id)
        # In quest_street_debt.json, debt__corner_fight (pk=21) is combat.
        self.combat_scene = Scene.objects.get(key='debt__corner_fight')
        self.session.current_scene = self.combat_scene
        self.session.save()
        
        # Create CombatState
        from .models import CombatEncounter, CombatState
        encounter = CombatEncounter.objects.get(scene=self.combat_scene)
        self.combat_state = CombatState.objects.create(
            session=self.session,
            enemy=encounter.enemy,
            enemy_hp=encounter.enemy.max_hp,
            is_active=True
        )

    def test_combat_attack_continues(self):
        # Ensure enemy has enough HP to survive one hit
        self.combat_state.enemy_hp = 100
        self.combat_state.save()
        
        response = self.client.post(reverse('combat_attack'), HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        # Response should contain combat state markup (e.g. combat-panel)
        self.assertContains(response, "combat-panel")
        self.assertContains(response, self.combat_state.enemy.name.upper())

    def test_combat_victory_and_quest_completion(self):
        # Manipulate enemy HP to 1
        self.combat_state.enemy_hp = 1
        self.combat_state.save()
        
        # Ensure player has enough strength to actually hit if the mock fails for some reason
        self.session.stats.strength = 20
        self.session.stats.save()
        
        # Make sure player can hit and kill. 
        from unittest.mock import patch
        with patch('game.views.roll_d20', return_value=20):
            response = self.client.post(reverse('combat_attack'), HTTP_HX_REQUEST='true')
        
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        
        # Should have advanced to victory scene
        # victory_scene for corner_boy is 22 (debt__enforcer_fight)
        self.assertEqual(self.session.current_scene.pk, 22)
        
        # Assert CompletedQuest is created if victory scene is an ending
        if self.session.current_scene.is_ending:
            self.assertTrue(CompletedQuest.objects.filter(session=self.session, quest__key='street_debt').exists())

class LevelUpTest(TestCase):
    fixtures = ['game/fixtures/hub.json', 'game/fixtures/quest_warehouse_job.json']

    def setUp(self):
        self.client = Client()
        self.client.get('/game/')
        self.session = GameSession.objects.first()
        self.stats = self.session.stats

    def test_level_up_success(self):
        self.stats.stat_points = 1
        self.stats.strength = 10
        self.stats.save()
        
        response = self.client.post(
            reverse('level_up'),
            {'stat': 'muscle'},
            HTTP_HX_REQUEST='true'
        )
        
        self.assertEqual(response.status_code, 200)
        self.stats.refresh_from_db()
        self.assertEqual(self.stats.strength, 11)
        self.assertEqual(self.stats.stat_points, 0)
        self.assertIn('id="stats-bar"', response.content.decode())

    def test_level_up_no_points(self):
        self.stats.stat_points = 0
        self.stats.save()
        
        response = self.client.post(
            reverse('level_up'),
            {'stat': 'muscle'},
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(response.status_code, 400)

class UseItemTest(TestCase):
    fixtures = ['game/fixtures/hub.json', 'game/fixtures/quest_warehouse_job.json', 'game/fixtures/items.json']

    def setUp(self):
        self.client = Client()
        self.client.get('/game/')
        self.session = GameSession.objects.first()
        self.stats = self.session.stats
        
        from .models import Item, PlayerInventory
        # Let's create a heal item manually to be sure it has the effect_type
        self.heal_potion = Item.objects.create(
            key='test_potion',
            name='Test Potion',
            description='Heals you.',
            is_consumable=True,
            effect_type='heal_hp',
            effect_value=10
        )
        self.inventory_item = PlayerInventory.objects.create(
            session=self.session,
            item=self.heal_potion,
            quantity=1
        )

    def test_use_item_success(self):
        self.stats.hp = self.stats.max_hp - 5
        self.stats.save()
        
        response = self.client.post(
            reverse('use_item', kwargs={'item_id': self.heal_potion.pk}),
            HTTP_HX_REQUEST='true'
        )
        
        self.assertEqual(response.status_code, 200)
        self.stats.refresh_from_db()
        # It should heal at least 1 HP (usually potion heals more)
        self.assertGreater(self.stats.hp, self.stats.max_hp - 5)
        self.assertLessEqual(self.stats.hp, self.stats.max_hp)
        
        # Consumable should be removed
        from .models import PlayerInventory
        self.assertFalse(PlayerInventory.objects.filter(session=self.session, item=self.heal_potion).exists())

    def test_use_item_not_in_inventory(self):
        # Delete item from inventory first
        self.inventory_item.delete()
        
        response = self.client.post(
            reverse('use_item', kwargs={'item_id': self.heal_potion.pk}),
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(response.status_code, 400)

class NoticeBoardTest(TestCase):
    fixtures = ['game/fixtures/hub.json', 'game/fixtures/quest_warehouse_job.json']

    def setUp(self):
        self.client = Client()
        self.client.get('/game/')
        self.session = GameSession.objects.first()
        self.warehouse_job     = Quest.objects.get(key='the_warehouse_job')
        self.warehouse_entrance = Scene.objects.get(key='warehouse__loading_dock')

    def test_notice_board_initial_state(self):
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'hub__notice_board'}))
        self.assertContains(response, "[ AVAILABLE JOBS ]")
        self.assertContains(response, "The Warehouse Job")
        self.assertIn('quest-entry--available', response.content.decode())

    def test_quest_prerequisite_gating(self):
        # Create second quest requiring warehouse job
        from .models import Requirement, RequirementGroup
        second_quest = Quest.objects.create(
            key='second_quest',
            title='The Second Quest',
            description='Locked until warehouse is done.',
            entrance_scene=self.warehouse_entrance
        )
        req = Requirement.objects.create(
            condition_type='quest_completed',
            required_quest=self.warehouse_job
        )
        group = RequirementGroup.objects.create(
            label='Requires Warehouse',
            logic='all'
        )
        group.requirements.add(req)
        second_quest.requirements.add(group)
        
        # Check it's locked
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'hub__notice_board'}))
        self.assertContains(response, "[ LOCKED JOBS ]")
        self.assertContains(response, second_quest.title)
        self.assertContains(response, "Requires Warehouse")
        
        # Complete warehouse job
        CompletedQuest.objects.create(session=self.session, quest=self.warehouse_job, ending_type='victory')
        
        # Check it's now available
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'hub__notice_board'}))
        self.assertContains(response, second_quest.title)
        self.assertNotContains(response, "Requires Warehouse")

    def test_stat_gated_quest(self):
        # Create third quest requiring intellect 9
        from .models import Requirement, RequirementGroup
        intellect_quest = Quest.objects.create(
            key='intellect_quest',
            title='Intellect Quest',
            description='Requires brains.',
            entrance_scene=self.warehouse_entrance
        )
        req = Requirement.objects.create(
            condition_type='stat_gte',
            stat_name='intellect',
            stat_value=9
        )
        group = RequirementGroup.objects.create(
            label='Requires Intellect 9',
            logic='all'
        )
        group.requirements.add(req)
        intellect_quest.requirements.add(group)
        
        # Initial stats: intellect is 5
        self.session.stats.intellect = 6
        self.session.stats.save()
        
        # Check it's locked
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'hub__notice_board'}))
        self.assertContains(response, "Requires Intellect 9")
        
        # Raise intellect to 9
        self.session.stats.intellect = 9
        self.session.stats.save()
        
        # Check it's available
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'hub__notice_board'}))
        self.assertNotContains(response, "Requires Intellect 9")
        self.assertContains(response, intellect_quest.title)

    def test_completed_quest_rendering(self):
        # Make quest repeatable
        self.warehouse_job.is_repeatable = True
        self.warehouse_job.save()
        
        # Complete warehouse job
        cq = CompletedQuest.objects.create(session=self.session, quest=self.warehouse_job, ending_type='victory')
        
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'hub__notice_board'}))
        self.assertContains(response, "[ COMPLETED JOBS ]")
        self.assertContains(response, "The Warehouse Job")
        self.assertContains(response, "Victory")
        # self.assertContains(response, cq.completed_at.strftime("%b %d, %Y"))
        self.assertContains(response, "Play again")

    def test_start_quest_view(self):
        # Try to start locked quest (by stat)
        from .models import Requirement, RequirementGroup
        locked_quest = Quest.objects.create(
            key='locked_quest',
            title='Locked Quest',
            description='Requires brains.',
            entrance_scene=self.warehouse_entrance
        )
        req = Requirement.objects.create(
            condition_type='stat_gte',
            stat_name='intellect',
            stat_value=99
        )
        group = RequirementGroup.objects.create(
            label='Requires Big Brains',
            logic='all'
        )
        group.requirements.add(req)
        locked_quest.requirements.add(group)
        
        response = self.client.post(reverse('start_quest', kwargs={'quest_key': 'locked_quest'}))
        self.assertEqual(response.status_code, 403)
        
        # Start available quest
        response = self.client.post(reverse('start_quest', kwargs={'quest_key': 'the_warehouse_job'}))
        self.assertRedirects(response, reverse('scene_detail', kwargs={'scene_key': self.warehouse_entrance.key}))
        
        # Check session advanced
        self.session.refresh_from_db()
        self.assertEqual(self.session.current_scene, self.warehouse_entrance)
        
        # Check log
        self.assertTrue(self.session.log.filter(text__icontains="took the job").exists())

    def test_start_quest_htmx(self):
        response = self.client.post(
            reverse('start_quest', kwargs={'quest_key': 'the_warehouse_job'}),
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="scene-panel"', response.content.decode())
        self.assertContains(response, self.warehouse_entrance.title)

