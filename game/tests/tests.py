from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from game.models import (
    Scene, GameSession, PlayerStats, Choice, Quest, CompletedQuest,
    Requirement, RequirementGroup, PlayerContext,
)
from game.constants import SESSION_KEY
from .test_factories import make_game_session, make_hub_scene, make_item
from game.models import Enemy

class GameNavigationTest(TestCase):
    def setUp(self):
        self.client = Client()
        hub = make_hub_scene()

        notice_board = Scene.objects.create(
            key='hub__notice_board', title='The Board', body='', scene_type='hub',
        )
        Choice.objects.create(
            scene=notice_board, label='Head back outside', target_scene=hub, order=1,
        )

        self.warehouse_scene = Scene.objects.create(
            key='warehouse__loading_dock', title='Loading Dock', body='', scene_type='normal',
        )
        Choice.objects.create(
            scene=self.warehouse_scene, label='Slip around back.', target_scene=hub, order=1,
        )

        decoy = Scene.objects.create(key='test__nav_decoy', title='Decoy', body='', scene_type='normal')
        Choice.objects.create(scene=decoy, label='Decoy Choice', target_scene=hub, order=1)

    def test_root_redirects_to_game(self):
        response = self.client.get('/')
        self.assertRedirects(response, '/game/', target_status_code=302)

    def test_game_hub_creates_session_and_redirects(self):
        response = self.client.get('/game/')
        self.assertRedirects(response, reverse('scene_detail', kwargs={'scene_key': 'hub__apartment'}))
        
        # Check if session was created in DB
        self.assertEqual(GameSession.objects.count(), 1)
        # Check if stats were created
        self.assertEqual(PlayerStats.objects.count(), 1)
        # Check if session ID is in request.session
        self.assertIn(SESSION_KEY, self.client.session)

    def test_scene_navigation(self):
        self.client.get('/game/')
        session = GameSession.objects.first()
        initial_scene = session.current_scene

        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'hub__notice_board'}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The Board")
        self.assertContains(response, "Head back outside")
        session.refresh_from_db()
        self.assertEqual(session.current_scene, initial_scene)

    def test_stat_gated_choice(self):
        # Initialize session
        self.client.get('/game/')
        game_session = GameSession.objects.first()
        stats = game_session.stats
        
        # Warehouse Job entrance scene
        scene = Scene.objects.get(key='warehouse__loading_dock')
        
        choice_sneak = Choice.objects.get(
            scene=scene,
            label__icontains='Slip around back',
        )
        
        # Create a Requirement for agility 7
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
        session_id_1 = self.client.session[SESSION_KEY]
        
        # Second visit
        self.client.get('/game/')
        session_id_2 = self.client.session[SESSION_KEY]
        
        self.assertEqual(session_id_1, session_id_2)
        self.assertEqual(GameSession.objects.count(), 1)

    def test_choice_resolve_advances_scene_and_returns_htmx_fragment(self):
        self.client.get('/game/')
        session = GameSession.objects.first()
        initial_scene = session.current_scene

        # Create a choice on the current scene pointing to a new scene
        dest = Scene.objects.create(
            key='test__nav_dest', title='Destination', body='', scene_type='normal',
        )
        choice = Choice.objects.create(
            scene=initial_scene, label='Go there', target_scene=dest, order=1,
        )

        response = self.client.post(
            reverse('choice_resolve', kwargs={'choice_id': choice.pk}),
            HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="scene-panel"', response.content.decode())
        session.refresh_from_db()
        self.assertEqual(session.current_scene, dest)

    def test_choice_flag_effects_update_gated_choice_visibility(self):
        self.client.get('/game/')
        session = GameSession.objects.first()
        current_scene = session.current_scene

        next_scene = Scene.objects.create(
            key='phase6__flag_next',
            title='Flag Next',
            body='next',
            scene_type='normal',
        )
        final_scene = Scene.objects.create(
            key='phase6__flag_final',
            title='Flag Final',
            body='final',
            scene_type='normal',
        )
        set_flag_choice = Choice.objects.create(
            scene=current_scene,
            label='Set Secret Flag',
            target_scene=next_scene,
            set_flag_name='phase6_secret',
            order=9000,
        )
        clear_flag_choice = Choice.objects.create(
            scene=current_scene,
            label='Clear Secret Flag',
            target_scene=next_scene,
            clear_flag_name='phase6_secret',
            order=9001,
        )
        gated_choice = Choice.objects.create(
            scene=current_scene,
            label='Secret Route',
            target_scene=final_scene,
            order=9002,
        )

        gate_req = Requirement.objects.create(
            condition_type='has_flag',
            flag_name='phase6_secret',
        )
        gate_group = RequirementGroup.objects.create(
            label='Requires phase6_secret',
            logic='all',
        )
        gate_group.requirements.add(gate_req)
        gated_choice.requirements.add(gate_group)

        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': current_scene.key}))
        self.assertNotContains(response, gated_choice.label)

        self.client.post(
            reverse('choice_resolve', kwargs={'choice_id': set_flag_choice.pk}),
            HTTP_HX_REQUEST='true',
        )
        session.refresh_from_db()
        self.assertTrue(session.flags.get('phase6_secret'))

        session.current_scene = current_scene
        session.save(update_fields=['current_scene'])
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': current_scene.key}))
        self.assertContains(response, gated_choice.label)

        self.client.post(
            reverse('choice_resolve', kwargs={'choice_id': clear_flag_choice.pk}),
            HTTP_HX_REQUEST='true',
        )
        session.refresh_from_db()
        self.assertNotIn('phase6_secret', session.flags)

        session.current_scene = current_scene
        session.save(update_fields=['current_scene'])
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': current_scene.key}))
        self.assertNotContains(response, gated_choice.label)

    def test_choice_resolve_rejects_choice_from_different_scene(self):
        self.client.get('/game/')
        session = GameSession.objects.first()
        initial_scene = session.current_scene

        off_scene_choice = Choice.objects.exclude(scene=initial_scene).first()
        self.assertIsNotNone(off_scene_choice, "Expected at least one choice from another scene")

        response = self.client.post(
            reverse('choice_resolve', kwargs={'choice_id': off_scene_choice.pk}),
            HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 403)
        session.refresh_from_db()
        self.assertEqual(session.current_scene, initial_scene)

class RequirementEvaluationTest(TestCase):
    def test_numeric_gte_conditions(self):
        from types import SimpleNamespace
        from ..models import PlayerContext
        cases = [
            ('stat_gte',  'strength', 10, SimpleNamespace(strength=10, level=5), True),
            ('stat_gte',  'strength', 11, SimpleNamespace(strength=10, level=5), False),
            ('level_gte', None,        5, SimpleNamespace(level=5),               True),
            ('level_gte', None,        6, SimpleNamespace(level=5),               False),
        ]
        for condition_type, stat_name, stat_value, stats, expected in cases:
            with self.subTest(condition_type=condition_type, stat_value=stat_value):
                ctx = PlayerContext(stats=stats, inventory={}, completed_map={})
                req = Requirement(condition_type=condition_type, stat_name=stat_name, stat_value=stat_value)
                self.assertEqual(req.evaluate(ctx), expected)

    def test_has_item_missing_item(self):
        from ..models import PlayerContext
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
        from ..models import PlayerContext
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
        from ..models import PlayerContext
        req = Requirement(condition_type='quest_ending', required_quest_id=1, required_ending_type='victory')
        
        ctx = PlayerContext(stats=None, inventory={}, completed_map={1: 'victory'})
        self.assertTrue(req.evaluate(ctx))
        ctx.completed_map = {1: 'defeat'}
        self.assertFalse(req.evaluate(ctx))
        ctx.completed_map = {2: 'victory'}
        self.assertFalse(req.evaluate(ctx))

    def test_requirement_group_logic(self):
        from ..models import PlayerContext
        
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
    fixtures = [
        'game/fixtures/property.json',
        'game/fixtures/scene.json',
        'game/fixtures/enemy.json',
        'game/fixtures/combatencounter.json',
    ]

    def setUp(self):
        from ..models import CombatEncounter, CombatState
        self.client = Client()
        self.client.get('/game/')
        session_id = self.client.session.session_key
        self.session = GameSession.objects.get(session_key=session_id)
        self.combat_scene = Scene.objects.get(key='debt__corner_fight')
        self.session.current_scene = self.combat_scene
        self.session.save()
        encounter = CombatEncounter.objects.get(scene=self.combat_scene)
        self.combat_state = CombatState.objects.create(
            session=self.session,
            enemy=encounter.enemy,
            enemy_hp=encounter.enemy.max_hp,
            is_active=True
        )

    def test_player_attack_non_killing_blow_returns_combat_panel(self):
        self.combat_state.enemy_hp = 100
        self.combat_state.save()

        with patch('game.services.combat.roll_d20', return_value=20):
            response = self.client.post(reverse('combat_attack'), HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "combat-panel")
        self.assertContains(response, self.combat_state.enemy.name.upper())
        self.combat_state.refresh_from_db()
        self.assertLess(self.combat_state.enemy_hp, 100)

    def test_combat_victory_and_quest_completion(self):
        self.combat_state.enemy_hp = 1
        self.combat_state.save()
        self.session.stats.strength = 20
        self.session.stats.save()

        # Step 1: killing blow sets pending_victory but stays on combat scene
        with patch('game.services.combat.roll_d20', return_value=20):
            self.client.post(reverse('combat_attack'), HTTP_HX_REQUEST='true')

        self.combat_state.refresh_from_db()
        self.assertTrue(self.combat_state.pending_victory)

        # Step 2: continue advances to the victory scene
        response = self.client.post(reverse('combat_continue'), HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        victory_scene = Scene.objects.get(key='debt__enforcer_fight')
        self.assertEqual(self.session.current_scene, victory_scene)

class LevelUpTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = make_game_session(self.client)
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

    def test_scene_renders_level_up_panel_after_level_gain(self):
        self.stats.level = 2
        self.stats.stat_points = 1
        self.stats.save()

        response = self.client.get(
            reverse('scene_detail', kwargs={'scene_key': self.session.current_scene.key})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MOVING UP")
        self.assertContains(response, "Word travels fast.")

    def test_scene_hides_level_up_panel_when_none_available(self):
        self.stats.stat_points = 0
        self.stats.save()

        response = self.client.get(
            reverse('scene_detail', kwargs={'scene_key': self.session.current_scene.key})
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "MOVING UP")

class UseItemTest(TestCase):
    def setUp(self):
        from ..models import Item, PlayerInventory
        self.client = Client()
        self.session = make_game_session(self.client)
        self.stats = self.session.stats
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
        self.assertEqual(self.stats.hp, self.stats.max_hp)
        
        # Consumable should be removed
        from ..models import PlayerInventory
        self.assertFalse(PlayerInventory.objects.filter(session=self.session, item=self.heal_potion).exists())

    def test_use_item_not_in_inventory(self):
        # Delete item from inventory first
        self.inventory_item.delete()
        
        response = self.client.post(
            reverse('use_item', kwargs={'item_id': self.heal_potion.pk}),
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(response.status_code, 400)

class QuestBuilderSceneTest(TestCase):
    """Tests for quest builder scene create/save/delete admin views."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.admin = User.objects.create_superuser(
            username='testadmin', password='testpass', email='a@a.com'
        )
        self.client = Client()
        self.client.force_login(self.admin)
        self.quest = Quest.objects.create(
            key='test_quest',
            title='Test Quest',
            description='A quest for testing.',
        )

    def _create_url(self):
        return reverse('admin:quest_builder_scene_create', args=[self.quest.pk])

    def _save_url(self, scene_id):
        return reverse('admin:quest_builder_scene_save', args=[self.quest.pk, scene_id])

    def _delete_url(self, scene_id):
        return reverse('admin:quest_builder_scene_delete', args=[self.quest.pk, scene_id])

    # ── CREATE ─────────────────────────────────────────────────────────────────

    def test_scene_create_saves_to_db(self):
        self.assertEqual(self.quest.scenes.count(), 0)

        response = self.client.post(self._create_url(), {
            'title': 'Rooftop',
            'key': 'test_quest__rooftop',
            'scene_type': 'normal',
            'description': 'High up.',
            'canvas_x': '100',
            'canvas_y': '200',
        })

        self.assertEqual(response.status_code, 200,
            f"Expected 200, got {response.status_code}. Body: {response.content[:400]}")
        self.assertEqual(self.quest.scenes.count(), 1)
        scene = self.quest.scenes.get()
        self.assertEqual(scene.title, 'Rooftop')
        self.assertEqual(scene.key, 'test_quest__rooftop')
        self.assertEqual(scene.canvas_x, 100)
        self.assertEqual(scene.canvas_y, 200)

    def test_scene_create_auto_generates_key(self):
        self.client.post(self._create_url(), {
            'title': 'Dark Alley',
            'key': '',
            'scene_type': 'normal',
            'description': '',
        })
        scene = self.quest.scenes.get()
        self.assertIn('test_quest', scene.key)
        self.assertIn('dark', scene.key)

    def test_scene_create_returns_oob_html(self):
        response = self.client.post(self._create_url(), {
            'title': 'Docks',
            'scene_type': 'normal',
            'description': '',
        })
        body = response.content.decode()
        self.assertIn('hx-swap-oob', body)
        self.assertIn('canvas-stage', body)
        self.assertIn('qb-toast-container', body)
        self.assertIn('Docks', body)

    def test_scene_create_get_not_allowed(self):
        response = self.client.get(self._create_url())
        self.assertEqual(response.status_code, 405)

    def test_scene_create_requires_login(self):
        self.client.logout()
        response = self.client.post(self._create_url(), {'title': 'X', 'scene_type': 'normal'})
        # Should redirect to admin login
        self.assertIn(response.status_code, [302, 403])

    # ── SAVE ───────────────────────────────────────────────────────────────────

    def test_scene_save_updates_db(self):
        scene = Scene.objects.create(
            quest=self.quest, key='test_quest__old', title='Old Title',
            body='old body', scene_type='normal',
        )
        response = self.client.post(self._save_url(scene.pk), {
            'title': 'New Title',
            'key': 'test_quest__new',
            'scene_type': 'hub',
            'description': 'new body',
        })
        self.assertEqual(response.status_code, 200,
            f"Expected 200, got {response.status_code}. Body: {response.content[:400]}")
        scene.refresh_from_db()
        self.assertEqual(scene.title, 'New Title')
        self.assertEqual(scene.scene_type, 'hub')
        self.assertEqual(scene.body, 'new body')

    def test_scene_save_returns_oob_html(self):
        scene = Scene.objects.create(
            quest=self.quest, key='test_quest__s', title='Spot',
            body='', scene_type='normal',
        )
        response = self.client.post(self._save_url(scene.pk), {
            'title': 'Spot', 'key': 'test_quest__s',
            'scene_type': 'normal', 'description': '',
        })
        body = response.content.decode()
        self.assertIn('hx-swap-oob', body)
        self.assertIn(f'scene-card-{scene.pk}', body)
        self.assertIn('qb-toast-container', body)

    # ── DELETE ─────────────────────────────────────────────────────────────────

    def test_scene_delete_removes_from_db(self):
        scene = Scene.objects.create(
            quest=self.quest, key='test_quest__del', title='Gone',
            body='', scene_type='normal',
        )
        # First POST shows confirmation; second POST with confirmed=1 executes the delete.
        self.client.post(self._delete_url(scene.pk))
        response = self.client.post(self._delete_url(scene.pk), {'confirmed': '1'})
        self.assertEqual(response.status_code, 200,
            f"Expected 200, got {response.content[:400]}")
        self.assertFalse(Scene.objects.filter(pk=scene.pk).exists())


class NoticeBoardTest(TestCase):
    fixtures = [
        'game/fixtures/arc.json',
        'game/fixtures/property.json',
        'game/fixtures/requirement.json',
        'game/fixtures/requirementgroup.json',
        'game/fixtures/scene.json',
        'game/fixtures/choice.json',
        'game/fixtures/quest.json',
    ]

    def setUp(self):
        self.client = Client()
        self.client.get('/game/')
        self.session = GameSession.objects.first()
        self.warehouse_job     = Quest.objects.get(key='the_warehouse_job')
        self.warehouse_entrance = Scene.objects.get(key='warehouse__loading_dock')
        self.notice_board_scene = Scene.objects.get(key='hub__notice_board')
        self.warehouse_job.hub_scenes.add(self.notice_board_scene)

    def test_notice_board_initial_state(self):
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'hub__notice_board'}))
        self.assertContains(response, "[ AVAILABLE JOBS ]")
        self.assertContains(response, "The Warehouse Job")
        self.assertIn('quest-entry--available', response.content.decode())

    def test_quest_prerequisite_gating(self):
        # Create second quest requiring warehouse job
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
        second_quest.hub_scenes.add(self.notice_board_scene)

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
        intellect_quest.hub_scenes.add(self.notice_board_scene)

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
        self.assertContains(response, "Play again")

    def test_start_quest_view(self):
        # Try to start locked quest (by stat)
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


class QueryBudgetTest(TestCase):
    fixtures = [
        'game/fixtures/arc.json',
        'game/fixtures/property.json',
        'game/fixtures/requirement.json',
        'game/fixtures/requirementgroup.json',
        'game/fixtures/scene.json',
        'game/fixtures/choice.json',
        'game/fixtures/quest.json',
    ]

    def setUp(self):
        self.client = Client()
        self.client.get('/game/')
        self.session = GameSession.objects.first()

    def test_get_available_choices_uses_prefetch_budget(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from ..services.scene import get_available_choices

        scene = Scene.objects.get(key='warehouse__loading_dock')
        with CaptureQueriesContext(connection) as ctx:
            choices = get_available_choices(scene, self.session.stats, {}, {})

        self.assertGreaterEqual(len(choices), 1)
        self.assertLessEqual(len(ctx), 4)

    def test_get_notice_board_uses_prefetch_budget(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from ..services.scene import get_notice_board

        scene = Scene.objects.get(key='hub__notice_board')
        with CaptureQueriesContext(connection) as ctx:
            board = get_notice_board(scene, {}, {}, self.session.stats)

        self.assertIn('available', board)
        self.assertIn('locked', board)
        self.assertIn('completed', board)
        self.assertLessEqual(len(ctx), 4)


class RivalContestTest(TestCase):
    fixtures = [
        'game/fixtures/arc.json',
        'game/fixtures/property.json',
        'game/fixtures/requirement.json',
        'game/fixtures/requirementgroup.json',
        'game/fixtures/scene.json',
        'game/fixtures/choice.json',
        'game/fixtures/quest.json',
    ]

    def setUp(self):
        self.client = Client()
        self.client.get('/game/')
        self.session = GameSession.objects.first()

    def test_process_turn_income_skips_save_when_no_logs(self):
        from ..services.property_service import process_turn_income

        with patch.object(self.session.stats, 'save') as stats_save:
            logs, totals = process_turn_income(self.session)

        self.assertEqual(logs, [])
        self.assertEqual(totals, {'cash': 0, 'heat': 0, 'rep': 0})
        stats_save.assert_not_called()

    def test_trigger_rival_contest_returns_none_without_contestable_properties(self):
        from ..services.property_service import trigger_rival_contest

        self.session.stats.heat = 200
        self.session.stats.save()
        with patch('game.services.property_service.random.random', return_value=0):
            log, unlocked = trigger_rival_contest(self.session)

        self.assertIsNone(log)
        self.assertIsNone(unlocked)

    def test_trigger_rival_contest_materializes_queryset_once(self):
        from ..models import Property, PlayerProperty, RivalClaim
        from ..services.property_service import trigger_rival_contest

        start_scene = Scene.objects.create(
            key='phase4__contest_start',
            title='Phase4 Start',
            body='start',
            scene_type='normal',
        )
        resolution_scene = Scene.objects.create(
            key='phase4__contest_resolution',
            title='Phase4 Resolution',
            body='resolve',
            scene_type='normal',
        )
        self.session.current_scene = start_scene
        self.session.save(update_fields=['current_scene'])
        self.session.stats.heat = 200
        self.session.stats.save()

        prop = Property.objects.create(
            key='phase4_property',
            name='Phase4 Property',
            property_type='business',
            cash_per_turn=5,
            heat_per_turn=1,
            rep_per_turn=1,
            is_contestable=True,
            resolution_scene=resolution_scene,
        )
        player_property = PlayerProperty.objects.create(
            session=self.session,
            property=prop,
            is_contested=False,
        )

        with patch('game.services.property_service.random.random', return_value=0), patch(
            'game.services.property_service.random.choice', side_effect=lambda seq: seq[0]
        ) as mock_choice:
            log, unlocked = trigger_rival_contest(self.session)

        self.assertIsNotNone(log)
        self.assertEqual(unlocked, resolution_scene)
        self.assertTrue(PlayerProperty.objects.filter(pk=player_property.pk, is_contested=True).exists())
        self.assertTrue(
            RivalClaim.objects.filter(
                player_property=player_property,
                resolution_scene=resolution_scene
            ).exists()
        )
        self.assertEqual(mock_choice.call_count, 1)
        self.assertIsInstance(mock_choice.call_args.args[0], list)

    def test_resolve_contest_victory_clears_claim_and_contested_flag(self):
        from ..models import Property, PlayerProperty, RivalClaim
        from ..services.property_service import resolve_contest

        resolution_scene = Scene.objects.create(
            key='phase6__contest_victory_resolution',
            title='Victory Resolution',
            body='resolve',
            scene_type='ending',
            ending_type='victory',
        )
        prop = Property.objects.create(
            key='phase6_victory_property',
            name='Phase6 Victory Property',
            property_type='business',
            cash_per_turn=2,
            is_contestable=True,
            resolution_scene=resolution_scene,
        )
        player_property = PlayerProperty.objects.create(
            session=self.session,
            property=prop,
            is_contested=True,
        )
        claim = RivalClaim.objects.create(
            player_property=player_property,
            resolution_scene=resolution_scene,
        )

        log = resolve_contest(self.session, claim, 'victory')

        player_property.refresh_from_db()
        self.assertFalse(player_property.is_contested)
        self.assertFalse(RivalClaim.objects.filter(pk=claim.pk).exists())
        self.assertIn('is yours again', log)

    def test_resolve_contest_non_victory_removes_property_and_claim(self):
        from ..models import Property, PlayerProperty, RivalClaim
        from ..services.property_service import resolve_contest

        resolution_scene = Scene.objects.create(
            key='phase6__contest_defeat_resolution',
            title='Defeat Resolution',
            body='resolve',
            scene_type='ending',
            ending_type='defeat',
        )
        prop = Property.objects.create(
            key='phase6_defeat_property',
            name='Phase6 Defeat Property',
            property_type='business',
            cash_per_turn=2,
            is_contestable=True,
            resolution_scene=resolution_scene,
        )
        player_property = PlayerProperty.objects.create(
            session=self.session,
            property=prop,
            is_contested=True,
        )
        claim = RivalClaim.objects.create(
            player_property=player_property,
            resolution_scene=resolution_scene,
        )

        log = resolve_contest(self.session, claim, 'defeat')

        self.assertFalse(PlayerProperty.objects.filter(pk=player_property.pk).exists())
        self.assertFalse(RivalClaim.objects.filter(pk=claim.pk).exists())
        self.assertIn('is gone', log)


class EffectiveStatsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = make_game_session(self.client)

    def test_get_effective_stats_applies_passive_item_bonuses(self):
        from ..models import Item, PlayerInventory
        from ..utils import get_effective_stats

        stats = self.session.stats
        stats.strength = 8
        stats.agility = 7
        stats.save()

        str_item = Item.objects.create(
            key='phase6__str_charm',
            name='STR Charm',
            description='Passive strength bonus.',
            passive_stat='strength',
            passive_value=2,
        )
        agi_item = Item.objects.create(
            key='phase6__agi_charm',
            name='AGI Charm',
            description='Passive agility bonus.',
            passive_stat='agility',
            passive_value=3,
        )
        second_str_item = Item.objects.create(
            key='phase6__str_charm_2',
            name='STR Charm 2',
            description='Another passive strength bonus.',
            passive_stat='strength',
            passive_value=1,
        )
        PlayerInventory.objects.create(session=self.session, item=str_item, quantity=1)
        PlayerInventory.objects.create(session=self.session, item=agi_item, quantity=1)
        PlayerInventory.objects.create(session=self.session, item=second_str_item, quantity=1)

        from ..services.inventory import get_player_inventory
        inventory = get_player_inventory(self.session)
        effective = get_effective_stats(stats, inventory)

        self.assertEqual(effective.strength, 11)
        self.assertEqual(effective.agility, 10)
        self.assertEqual(effective.bonuses['strength'], 3)
        self.assertEqual(effective.bonuses['agility'], 3)


class ProgressionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = make_game_session(self.client)
        self.stats = self.session.stats

    def test_award_xp_crosses_multiple_levels(self):
        from ..services.progression import award_xp

        self.stats.level = 1
        self.stats.experience = 150
        self.stats.stat_points = 0
        self.stats.stat_points_awarded = 0
        self.stats.save()

        levels = award_xp(self.session, self.stats, 500)
        self.stats.refresh_from_db()

        self.assertEqual(levels, [2, 3])
        self.assertEqual(self.stats.level, 3)
        self.assertEqual(self.stats.experience, 650)
        self.assertEqual(self.stats.stat_points, 6)
        self.assertEqual(self.stats.stat_points_awarded, 6)

    def test_award_xp_irregular_increments_do_not_over_or_under_grant_points(self):
        from ..services.progression import award_xp

        self.stats.experience = 0
        self.stats.stat_points = 0
        self.stats.stat_points_awarded = 0
        self.stats.save()

        award_xp(self.session, self.stats, 7)
        award_xp(self.session, self.stats, 133)
        award_xp(self.session, self.stats, 250)
        self.stats.refresh_from_db()

        self.assertEqual(self.stats.experience, 390)
        self.assertEqual(self.stats.stat_points, 3)
        self.assertEqual(self.stats.stat_points_awarded, 3)

    def test_award_xp_catches_up_legacy_rows_on_first_post_migration_xp_gain(self):
        from ..services.progression import award_xp

        self.stats.experience = 550
        self.stats.stat_points = 0
        self.stats.stat_points_awarded = 0
        self.stats.save()

        award_xp(self.session, self.stats, 1)
        self.stats.refresh_from_db()

        self.assertEqual(self.stats.experience, 551)
        self.assertEqual(self.stats.stat_points, 5)
        self.assertEqual(self.stats.stat_points_awarded, 5)


class QuestBuilderValidationTest(TestCase):
    """Tests for validate_quest() using factory-created objects — no fixtures."""

    def _make_quest(self, key='qbv__quest', **kwargs):
        return Quest.objects.create(key=key, title='QB Quest', description='', **kwargs)

    def _make_scene(self, quest, key, scene_type='normal', **kwargs):
        return Scene.objects.create(quest=quest, key=key, title=key, body='', scene_type=scene_type, **kwargs)

    def _make_choice(self, scene, label='Go', **kwargs):
        return Choice.objects.create(scene=scene, label=label, order=1, **kwargs)

    def _warning_types(self, quest):
        from ..services.quest_builder import validate_quest
        return [w['type'] for w in validate_quest(quest.pk)]

    # ── Task 9.1: orphan scene ──────────────────────────────────────────────────

    def test_orphan_scene_detected(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, 'qbv__entry')
        quest.entrance_scene = entry
        quest.save()
        orphan = self._make_scene(quest, 'qbv__orphan')

        self.assertIn('orphan_scene', self._warning_types(quest))

    def test_no_orphan_when_pointed_to(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, 'qbv__e')
        dest  = self._make_scene(quest, 'qbv__d', scene_type='ending')
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, target_scene=dest)

        types = self._warning_types(quest)
        self.assertNotIn('orphan_scene', types)

    # ── Task 9.2: missing routing ───────────────────────────────────────────────

    def test_missing_routing_detected(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, 'qbv__e2')
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, label='Nowhere')  # no target set

        self.assertIn('missing_routing', self._warning_types(quest))

    def test_no_missing_routing_when_target_set(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, 'qbv__e3')
        dest  = self._make_scene(quest, 'qbv__d3', scene_type='ending')
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, target_scene=dest)

        self.assertNotIn('missing_routing', self._warning_types(quest))

    # ── Task 9.3: missing roll target ──────────────────────────────────────────

    def test_missing_roll_target_detected(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, 'qbv__e4', requires_roll=True)
        quest.entrance_scene = entry
        quest.save()
        # Choice with only success set — no failure
        dest = self._make_scene(quest, 'qbv__d4', scene_type='ending')
        self._make_choice(entry, success_scene=dest)

        self.assertIn('missing_roll_target', self._warning_types(quest))

    def test_no_missing_roll_target_when_both_set(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, 'qbv__e5', requires_roll=True)
        win   = self._make_scene(quest, 'qbv__w5', scene_type='ending')
        lose  = self._make_scene(quest, 'qbv__l5', scene_type='ending')
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, success_scene=win, failure_scene=lose)

        self.assertNotIn('missing_roll_target', self._warning_types(quest))

    # ── Task 9.4: roll scene with direct choice ─────────────────────────────────

    def test_roll_direct_choice_detected(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, 'qbv__e6', requires_roll=True)
        win   = self._make_scene(quest, 'qbv__w6', scene_type='ending')
        lose  = self._make_scene(quest, 'qbv__l6', scene_type='ending')
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, success_scene=win, failure_scene=lose)
        # Add a stray direct-target choice on the roll scene
        direct = self._make_scene(quest, 'qbv__direct6', scene_type='ending')
        self._make_choice(entry, label='Direct', target_scene=direct)

        self.assertIn('roll_direct_choice', self._warning_types(quest))

    # ── Task 9.5: empty non-ending scene ───────────────────────────────────────

    def test_empty_scene_detected(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, 'qbv__e7')
        empty = self._make_scene(quest, 'qbv__empty7')
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, target_scene=empty)  # points to empty, no choices on empty

        self.assertIn('empty_scene', self._warning_types(quest))

    def test_ending_scene_no_empty_warning(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, 'qbv__e8')
        end   = self._make_scene(quest, 'qbv__end8', scene_type='ending')
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, target_scene=end)

        self.assertNotIn('empty_scene', self._warning_types(quest))

    # ── Task 9.6: combat scene missing encounter ────────────────────────────────

    def test_combat_missing_encounter_detected(self):
        quest = self._make_quest()
        entry  = self._make_scene(quest, 'qbv__e9')
        combat = self._make_scene(quest, 'qbv__combat9', scene_type='combat')
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, target_scene=combat)

        self.assertIn('combat_missing_encounter', self._warning_types(quest))

    # ── Task 9.7: ending scene with no hub-return choice ───────────────────────

    def test_ending_no_hub_return_detected(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, 'qbv__e10')
        end   = self._make_scene(quest, 'qbv__end10', scene_type='ending')
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, target_scene=end)
        # ending has no choice pointing to a hub scene

        self.assertIn('ending_no_hub_return', self._warning_types(quest))

    def test_ending_with_hub_return_no_warning(self):
        hub   = Scene.objects.create(key='qbv__hub', title='Hub', body='', scene_type='hub')
        quest = self._make_quest(key='qbv__quest2')
        entry = self._make_scene(quest, 'qbv__e11')
        end   = self._make_scene(quest, 'qbv__end11', scene_type='ending')
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, target_scene=end)
        self._make_choice(end, label='Return', target_scene=hub)

        self.assertNotIn('ending_no_hub_return', self._warning_types(quest))



class MaxHpTest(TestCase):
    def test_create_session_sets_hp_and_max_hp_from_formula(self):
        from ..utils import compute_max_hp
        client = Client()
        session = make_game_session(client)
        stats = session.stats
        expected = compute_max_hp(5)
        self.assertEqual(stats.max_hp, expected)
        self.assertEqual(stats.hp, expected)

    def test_effective_stats_max_hp_reflects_strength_item_bonus(self):
        from ..models.items import Item
        from ..models import PlayerInventory
        from ..utils import get_effective_stats, compute_max_hp
        from ..services.inventory import get_player_inventory

        client = Client()
        session = make_game_session(client)
        stats = session.stats
        stats.strength = 10
        stats.max_hp = compute_max_hp(10)
        stats.save()

        str_item = Item.objects.create(
            key='maxhp__str_charm',
            name='STR Charm',
            description='',
            passive_stat='strength',
            passive_value=2,
        )
        PlayerInventory.objects.create(session=session, item=str_item, quantity=1)

        inventory = get_player_inventory(session)
        effective = get_effective_stats(stats, inventory)

        self.assertEqual(effective.strength, 12)
        self.assertEqual(effective.max_hp, compute_max_hp(12))
        self.assertEqual(stats.max_hp, compute_max_hp(10))

    def test_spend_strength_updates_max_hp_and_caps_hp(self):
        from ..utils import compute_max_hp
        from ..services.progression import spend_stat_point
        from ..constants import STAT_FIELD_MAP

        client = Client()
        session = make_game_session(client)
        stats = session.stats
        stats.strength = 10
        stats.max_hp = compute_max_hp(10)
        stats.hp = compute_max_hp(10)
        stats.stat_points = 1
        stats.save()

        spend_stat_point(stats, 'muscle', STAT_FIELD_MAP)
        stats.refresh_from_db()

        self.assertEqual(stats.strength, 11)
        self.assertEqual(stats.max_hp, compute_max_hp(11))
        self.assertLessEqual(stats.hp, stats.max_hp)


# =============================================================================
# Section 2 — Missing Tests (High Priority)
# =============================================================================


class CombatServiceTest(TestCase):
    """Direct service-level tests for execute_enemy_attack and initialize_combat_state."""

    def setUp(self):
        from ..models.combat import CombatEncounter
        self.client = Client()
        self.session = make_game_session(self.client)
        self.stats = self.session.stats

        self.enemy = Enemy.objects.create(
            key='cs__enemy', name='Corner Thug', description='',
            max_hp=20, attack_modifier=0, defense=8,
            damage_min=2, damage_max=4,
        )
        self.defeat_scene = Scene.objects.create(
            key='cs__defeat', title='Defeat', body='', scene_type='ending', ending_type='defeat',
        )
        self.victory_scene = Scene.objects.create(
            key='cs__victory', title='Victory', body='', scene_type='normal',
        )
        self.combat_scene = Scene.objects.create(
            key='cs__combat', title='Combat', body='', scene_type='combat',
        )
        self.encounter = CombatEncounter.objects.create(
            scene=self.combat_scene,
            enemy=self.enemy,
            victory_scene=self.victory_scene,
            defeat_scene=self.defeat_scene,
        )
        self.session.current_scene = self.combat_scene
        self.session.save()

    def _make_combat_state(self, **kwargs):
        from ..models.combat import CombatState
        defaults = dict(session=self.session, enemy=self.enemy, enemy_hp=20, turn_number=1, is_active=True)
        defaults.update(kwargs)
        return CombatState.objects.create(**defaults)

    def test_enemy_attack_hit_reduces_player_hp(self):
        from ..services.combat import execute_enemy_attack
        cs = self._make_combat_state(
            pending_enemy_roll=10,
            pending_enemy_total=12,
            pending_enemy_hit=True,
            pending_enemy_damage=3,
        )
        self.stats.hp = 10
        self.stats.save()

        execute_enemy_attack(self.session, self.stats, {}, {}, cs, self.stats)

        self.stats.refresh_from_db()
        self.assertEqual(self.stats.hp, 7)
        cs.refresh_from_db()
        self.assertEqual(cs.turn_number, 2)
        self.assertFalse(cs.enemy_attack_pending)

    def test_enemy_attack_miss_leaves_hp_unchanged(self):
        from ..services.combat import execute_enemy_attack
        cs = self._make_combat_state(
            pending_enemy_roll=1,
            pending_enemy_total=1,
            pending_enemy_hit=False,
            pending_enemy_damage=0,
        )
        self.stats.hp = 10
        self.stats.save()

        execute_enemy_attack(self.session, self.stats, {}, {}, cs, self.stats)

        self.stats.refresh_from_db()
        self.assertEqual(self.stats.hp, 10)
        cs.refresh_from_db()
        self.assertEqual(cs.turn_number, 2)

    def test_enemy_attack_reduces_player_to_zero_transitions_to_defeat_scene(self):
        from ..services.combat import execute_enemy_attack
        cs = self._make_combat_state(
            pending_enemy_roll=15,
            pending_enemy_total=17,
            pending_enemy_hit=True,
            pending_enemy_damage=5,
        )
        self.stats.hp = 2
        self.stats.save()

        execute_enemy_attack(self.session, self.stats, {}, {}, cs, self.stats)

        self.stats.refresh_from_db()
        self.assertEqual(self.stats.hp, 0)
        self.session.refresh_from_db()
        self.assertEqual(self.session.current_scene, self.defeat_scene)
        cs.refresh_from_db()
        self.assertFalse(cs.is_active)

    def test_initialize_combat_state_deactivates_when_entering_non_combat_scene(self):
        from ..services.combat import initialize_combat_state
        cs = self._make_combat_state()
        normal_scene = Scene.objects.create(
            key='cs__normal', title='Normal', body='', scene_type='normal',
        )

        result = initialize_combat_state(self.session, normal_scene)

        self.assertEqual(result, (None, None))
        cs.refresh_from_db()
        self.assertFalse(cs.is_active)

    def test_initialize_combat_state_recreates_deleted_inactive_state(self):
        from ..models.combat import CombatState
        from ..services.combat import initialize_combat_state
        old_cs = self._make_combat_state(is_active=False)
        old_pk = old_cs.pk

        new_cs, init_log = initialize_combat_state(self.session, self.combat_scene)

        self.assertFalse(CombatState.objects.filter(pk=old_pk).exists())
        self.assertIsNotNone(new_cs)
        self.assertTrue(new_cs.is_active)
        self.assertIn(self.enemy.name, init_log)


class InventoryServiceTest(TestCase):
    """Unit tests for apply_item_effect, consume_item, award_scene_items, award_scene_contacts."""

    def setUp(self):
        self.client = Client()
        self.session = make_game_session(self.client)
        self.stats = self.session.stats

    def test_use_item_add_stat_effect_increases_stat_and_consumes_item(self):
        from ..models import PlayerInventory
        from ..services.inventory import apply_item_effect

        item = make_item(
            key='inv__add_str', name='Strength Tonic',
            is_consumable=True, effect_type='add_stat', effect_stat='strength', effect_value=2,
        )
        pi = PlayerInventory.objects.create(session=self.session, item=item, quantity=1)
        inventory = {item.id: pi}
        original_str = self.stats.strength

        apply_item_effect(self.session, self.stats, inventory, item)

        self.stats.refresh_from_db()
        self.assertEqual(self.stats.strength, original_str + 2)
        self.assertFalse(PlayerInventory.objects.filter(session=self.session, item=item).exists())

    def test_consume_item_decrements_quantity_without_deleting_when_qty_gt_1(self):
        from ..models import PlayerInventory
        from ..services.inventory import consume_item

        item = make_item(key='inv__multi', name='Multi Item')
        pi = PlayerInventory.objects.create(session=self.session, item=item, quantity=2)
        inventory = {item.id: pi}

        consume_item(self.session, item, inventory)

        pi.refresh_from_db()
        self.assertEqual(pi.quantity, 1)

    def test_award_scene_items_respects_award_once_flag(self):
        from ..models import PlayerInventory
        from ..models.world import SceneItem
        from ..services.inventory import award_scene_items

        scene = self.session.current_scene
        item = make_item(key='inv__award_once', name='Once Item')
        SceneItem.objects.create(scene=scene, item=item, quantity=1, award_once=True)

        inventory = {}
        award_scene_items(self.session, scene, inventory)
        award_scene_items(self.session, scene, inventory)

        pi = PlayerInventory.objects.get(session=self.session, item=item)
        self.assertEqual(pi.quantity, 1)

    def test_award_scene_contacts_gain_and_lose(self):
        from ..models.world import Contact, SceneContact
        from ..models.player import PlayerContact
        from ..services.inventory import award_scene_contacts

        scene = self.session.current_scene
        gained = Contact.objects.create(key='inv__c_gain', name='Gained Contact', description='')
        lost   = Contact.objects.create(key='inv__c_lose', name='Lost Contact',   description='')
        SceneContact.objects.create(scene=scene, contact=gained, action='gain', award_once=False)
        SceneContact.objects.create(scene=scene, contact=lost,   action='lose', award_once=False)

        existing_pc = PlayerContact.objects.create(session=self.session, contact=lost)
        contacts = {lost.id: existing_pc}

        awarded, removed = award_scene_contacts(self.session, scene, contacts)

        self.assertEqual([c.id for c in awarded], [gained.id])
        self.assertEqual([c.id for c in removed], [lost.id])
        self.assertTrue(PlayerContact.objects.filter(session=self.session, contact=gained).exists())
        self.assertFalse(PlayerContact.objects.filter(session=self.session, contact=lost).exists())


class PropertyServiceTest(TestCase):
    """Unit tests for apply_property_rewards and process_turn_income."""

    def setUp(self):
        self.client = Client()
        self.session = make_game_session(self.client)
        self.stats = self.session.stats

    def test_apply_property_rewards_grants_property_on_arrival(self):
        from ..models.property import Property, PlayerProperty
        from ..services.property_service import apply_property_rewards

        prop = Property.objects.create(key='test_bar', name='Test Bar', property_type='business')
        scene = Scene.objects.create(
            key='prop__receive', title='Receive', body='', scene_type='normal',
            receive_property=prop,
        )

        logs = apply_property_rewards(self.session, scene)

        self.assertTrue(PlayerProperty.objects.filter(session=self.session, property=prop).exists())
        self.assertEqual(len(logs), 1)
        self.assertIn('Test Bar', logs[0])

    def test_apply_property_rewards_skips_already_owned_property(self):
        from ..models.property import Property, PlayerProperty
        from ..services.property_service import apply_property_rewards

        prop = Property.objects.create(key='owned_bar', name='Owned Bar', property_type='business')
        PlayerProperty.objects.create(session=self.session, property=prop)
        scene = Scene.objects.create(
            key='prop__receive2', title='Receive2', body='', scene_type='normal',
            receive_property=prop,
        )

        apply_property_rewards(self.session, scene)

        self.assertEqual(PlayerProperty.objects.filter(session=self.session, property=prop).count(), 1)

    def test_apply_property_rewards_removes_property_on_lose(self):
        from ..models.property import Property, PlayerProperty
        from ..services.property_service import apply_property_rewards

        prop = Property.objects.create(key='lost_bar', name='Lost Bar', property_type='business')
        PlayerProperty.objects.create(session=self.session, property=prop)
        scene = Scene.objects.create(
            key='prop__lose', title='Lose', body='', scene_type='normal',
            lose_property=prop,
        )

        logs = apply_property_rewards(self.session, scene)

        self.assertFalse(PlayerProperty.objects.filter(session=self.session, property=prop).exists())
        self.assertEqual(len(logs), 1)
        self.assertIn('Lost Bar', logs[0])

    def test_process_turn_income_with_active_properties_applies_cash_rep_heat(self):
        from ..models.property import Property, PlayerProperty
        from ..services.property_service import process_turn_income

        prop = Property.objects.create(
            key='cash_cow',
            name='Cash Cow', property_type='business',
            cash_per_turn=100, heat_per_turn=5, rep_per_turn=3,
        )
        PlayerProperty.objects.create(session=self.session, property=prop)
        self.stats.cash = 0
        self.stats.heat = 20
        self.stats.rep = 0
        self.stats.save()

        logs, totals = process_turn_income(self.session)

        self.stats.refresh_from_db()
        self.assertEqual(self.stats.cash, 100)
        self.assertEqual(self.stats.heat, 15)  # max(0, 20 - 5)
        self.assertEqual(self.stats.rep, 3)
        self.assertGreater(len(logs), 0)
        self.assertIn('Cash Cow', logs[0])


class ProgressionServiceTest(TestCase):
    """Unit tests for maybe_complete_quest edge cases."""

    def setUp(self):
        self.client = Client()
        self.session = make_game_session(self.client)
        self.stats = self.session.stats

    def test_maybe_complete_quest_non_ending_scene_returns_empty(self):
        from ..models import CompletedQuest
        from ..services.progression import maybe_complete_quest

        normal_scene = Scene.objects.create(
            key='prog__normal', title='Normal', body='', scene_type='normal',
        )

        result = maybe_complete_quest(self.session, self.stats, normal_scene, {})

        self.assertEqual(result, [])
        self.assertFalse(CompletedQuest.objects.filter(session=self.session).exists())

    def test_maybe_complete_quest_already_completed_does_not_duplicate(self):
        from ..models import Quest, CompletedQuest
        from ..services.progression import maybe_complete_quest

        quest = Quest.objects.create(key='prog__quest', title='Prog Quest', description='')
        ending_scene = Scene.objects.create(
            quest=quest, key='prog__ending', title='Ending', body='', scene_type='ending', ending_type='victory',
        )
        CompletedQuest.objects.create(session=self.session, quest=quest, ending_type='victory')
        completed_map = {quest.id: 'victory'}

        result = maybe_complete_quest(self.session, self.stats, ending_scene, completed_map)

        self.assertEqual(result, [])
        self.assertEqual(CompletedQuest.objects.filter(session=self.session, quest=quest).count(), 1)


class ArrivalServiceTest(TestCase):
    """Integration tests for process_arrival quest-completion branch."""

    def setUp(self):
        self.client = Client()
        self.session = make_game_session(self.client)
        self.stats = self.session.stats

    def test_process_arrival_on_quest_ending_triggers_income_and_turn_summary(self):
        from ..models import Quest
        from ..services.arrival import process_arrival

        quest = Quest.objects.create(key='arr__quest', title='Arrival Quest', description='')
        ending_scene = Scene.objects.create(
            quest=quest, key='arr__ending', title='Ending', body='', scene_type='ending', ending_type='victory',
        )

        logs, turn_summary = process_arrival(self.session, self.stats, {}, {}, ending_scene)

        self.assertIsNotNone(turn_summary)
        self.assertIn('income_totals', turn_summary)
        combined = '\n'.join(logs)
        self.assertIn(quest.title, combined)

    def test_process_arrival_resolves_active_rival_claim_on_victory_scene(self):
        from ..models import Quest
        from ..models.property import Property, PlayerProperty, RivalClaim
        from ..services.arrival import process_arrival

        quest = Quest.objects.create(key='arr__quest2', title='Rival Quest', description='')
        ending_scene = Scene.objects.create(
            quest=quest, key='arr__victory', title='Victory', body='', scene_type='ending', ending_type='victory',
        )

        prop = Property.objects.create(key='contested_bar', name='Contested Bar', property_type='business')
        pp = PlayerProperty.objects.create(session=self.session, property=prop, is_contested=True)
        claim = RivalClaim.objects.create(player_property=pp, resolution_scene=ending_scene)

        logs, _ = process_arrival(self.session, self.stats, {}, {}, ending_scene)

        self.assertFalse(RivalClaim.objects.filter(pk=claim.pk).exists())
        self.assertIn('Rival backed down', '\n'.join(logs))


class CombatViewTest(TestCase):
    """View-level test for the combat enemy-attack endpoint."""

    def setUp(self):
        from ..models.combat import CombatEncounter, CombatState
        self.client = Client()
        self.session = make_game_session(self.client)
        self.stats = self.session.stats

        self.enemy = Enemy.objects.create(
            key='cview__enemy', name='View Thug', description='',
            max_hp=20, attack_modifier=0, defense=8,
            damage_min=2, damage_max=2,
        )
        self.victory_scene = Scene.objects.create(
            key='cview__victory', title='Victory', body='', scene_type='normal',
        )
        self.combat_scene = Scene.objects.create(
            key='cview__combat', title='Combat', body='', scene_type='combat',
        )
        CombatEncounter.objects.create(
            scene=self.combat_scene, enemy=self.enemy, victory_scene=self.victory_scene,
        )
        self.session.current_scene = self.combat_scene
        self.session.save()

        CombatState.objects.create(
            session=self.session, enemy=self.enemy, enemy_hp=self.enemy.max_hp,
            turn_number=1, is_active=True,
            pending_enemy_roll=5,
            pending_enemy_total=5,
            pending_enemy_hit=False,
            pending_enemy_damage=0,
        )

    def test_combat_enemy_attack_view_applies_queued_attack(self):
        from ..models.combat import CombatState
        initial_hp = self.stats.hp

        response = self.client.post(reverse('combat_resolve_enemy'), HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 200)
        cs = CombatState.objects.get(session=self.session)
        self.assertFalse(cs.enemy_attack_pending)
        self.assertEqual(cs.turn_number, 2)
        self.stats.refresh_from_db()
        self.assertEqual(self.stats.hp, initial_hp)  # miss — HP must be unchanged


class ExportGameStateTest(TestCase):
    """Smoke tests for build_game_state_payload."""

    def test_build_game_state_payload_returns_expected_structure(self):
        from ..services.export_game_state import build_game_state_payload

        payload = build_game_state_payload()

        self.assertIsInstance(payload, dict)
        for key in ('meta', 'counts', 'items', 'enemies', 'contacts', 'scenes', 'quests', 'jobs'):
            self.assertIn(key, payload)
        self.assertEqual(payload['meta']['version'], 1)
        self.assertIn('exported_at', payload['meta'])

    def test_build_game_state_payload_counts_match_list_lengths(self):
        from ..services.export_game_state import build_game_state_payload

        make_item(key='exp__item', name='Export Item')
        payload = build_game_state_payload()

        self.assertEqual(payload['counts']['items'],   len(payload['items']))
        self.assertEqual(payload['counts']['scenes'],  len(payload['scenes']))
        self.assertEqual(payload['counts']['enemies'], len(payload['enemies']))
