from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from .models import (
    Scene, GameSession, PlayerStats, Choice, Quest, CompletedQuest,
    Requirement, RequirementGroup, PlayerContext,
)
from .constants import SESSION_KEY
from .test_factories import make_game_session

class GameNavigationTest(TestCase):
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

    def test_htmx_choice_resolve(self):
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
    def test_stat_gte(self):
        from types import SimpleNamespace
        from .models import PlayerContext
        stats = SimpleNamespace(strength=10, level=5)
        ctx = PlayerContext(stats=stats, inventory={}, completed_map={})
        req = Requirement(condition_type='stat_gte', stat_name='strength', stat_value=10)
        self.assertTrue(req.evaluate(ctx))
        req.stat_value = 11
        self.assertFalse(req.evaluate(ctx))

    def test_has_item_missing_item(self):
        from .models import PlayerContext
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
        from .models import PlayerContext
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
        from .models import PlayerContext
        req = Requirement(condition_type='quest_ending', required_quest_id=1, required_ending_type='victory')
        
        ctx = PlayerContext(stats=None, inventory={}, completed_map={1: 'victory'})
        self.assertTrue(req.evaluate(ctx))
        ctx.completed_map = {1: 'defeat'}
        self.assertFalse(req.evaluate(ctx))
        ctx.completed_map = {2: 'victory'}
        self.assertFalse(req.evaluate(ctx))

    def test_level_gte(self):
        from types import SimpleNamespace
        from .models import PlayerContext
        stats = SimpleNamespace(level=5)
        ctx = PlayerContext(stats=stats, inventory={}, completed_map={})
        req = Requirement(condition_type='level_gte', stat_value=5)
        self.assertTrue(req.evaluate(ctx))
        req.stat_value = 6
        self.assertFalse(req.evaluate(ctx))

    def test_requirement_group_logic(self):
        from .models import PlayerContext
        
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
        from .models import CombatEncounter, CombatState
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

    def test_levelup_flavor_filter_uses_level_keyed_lookup(self):
        from .templatetags.game_filters import levelup_flavor

        self.assertEqual(levelup_flavor(2), "Word travels fast. You're moving up.")
        self.assertEqual(levelup_flavor(1), "")

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

class UseItemTest(TestCase):
    def setUp(self):
        from .models import Item, PlayerInventory
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
            key='test_quest__old', title='Old Title',
            body='old body', scene_type='normal',
        )
        self.quest.scenes.add(scene)
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
            key='test_quest__s', title='Spot',
            body='', scene_type='normal',
        )
        self.quest.scenes.add(scene)
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
            key='test_quest__del', title='Gone',
            body='', scene_type='normal',
        )
        self.quest.scenes.add(scene)
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


class Phase4PerformanceTest(TestCase):
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
        from .services.scene import get_available_choices

        scene = Scene.objects.get(key='warehouse__loading_dock')
        with CaptureQueriesContext(connection) as ctx:
            choices = get_available_choices(scene, self.session.stats, {}, {})

        self.assertGreaterEqual(len(choices), 1)
        self.assertLessEqual(len(ctx), 4)

    def test_get_notice_board_uses_prefetch_budget(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from .services.scene import get_notice_board

        scene = Scene.objects.get(key='hub__notice_board')
        with CaptureQueriesContext(connection) as ctx:
            board = get_notice_board(scene, {}, {}, self.session.stats)

        self.assertIn('available', board)
        self.assertIn('locked', board)
        self.assertIn('completed', board)
        self.assertLessEqual(len(ctx), 4)

    def test_process_turn_income_skips_save_when_no_logs(self):
        from .services.property_service import process_turn_income

        with patch.object(self.session.stats, 'save') as stats_save:
            logs, totals = process_turn_income(self.session)

        self.assertEqual(logs, [])
        self.assertEqual(totals, {'cash': 0, 'heat': 0, 'rep': 0})
        stats_save.assert_not_called()

    def test_trigger_rival_contest_returns_none_without_contestable_properties(self):
        from .services.property_service import trigger_rival_contest

        self.session.stats.heat = 200
        self.session.stats.save()
        with patch('game.services.property_service.random.random', return_value=0):
            log, unlocked = trigger_rival_contest(self.session)

        self.assertIsNone(log)
        self.assertIsNone(unlocked)

    def test_trigger_rival_contest_materializes_queryset_once(self):
        from .models import Property, PlayerProperty, RivalClaim
        from .services.property_service import trigger_rival_contest

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
        from .models import Property, PlayerProperty, RivalClaim
        from .services.property_service import resolve_contest

        resolution_scene = Scene.objects.create(
            key='phase6__contest_victory_resolution',
            title='Victory Resolution',
            body='resolve',
            scene_type='ending',
            ending_type='victory',
        )
        prop = Property.objects.create(
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
        from .models import Property, PlayerProperty, RivalClaim
        from .services.property_service import resolve_contest

        resolution_scene = Scene.objects.create(
            key='phase6__contest_defeat_resolution',
            title='Defeat Resolution',
            body='resolve',
            scene_type='ending',
            ending_type='defeat',
        )
        prop = Property.objects.create(
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
        from .models import Item, PlayerInventory
        from .utils import get_effective_stats

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

        from .services.inventory import get_player_inventory
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
        from .services.progression import award_xp

        self.stats.level = 1
        self.stats.experience = 150
        self.stats.stat_points = 0
        self.stats.save()

        levels = award_xp(self.session, self.stats, 500)
        self.stats.refresh_from_db()

        self.assertEqual(levels, [2, 3])
        self.assertEqual(self.stats.level, 3)
        self.assertEqual(self.stats.stat_points, 2)
        self.assertEqual(self.stats.experience, 650)


class QuestBuilderValidationTest(TestCase):
    """Tests for validate_quest() using factory-created objects — no fixtures."""

    def _make_quest(self, key='qbv__quest', **kwargs):
        return Quest.objects.create(key=key, title='QB Quest', description='', **kwargs)

    def _make_scene(self, quest, key, scene_type='normal', **kwargs):
        scene = Scene.objects.create(key=key, title=key, body='', scene_type=scene_type, **kwargs)
        quest.scenes.add(scene)
        return scene

    def _make_choice(self, scene, label='Go', **kwargs):
        return Choice.objects.create(scene=scene, label=label, order=1, **kwargs)

    def _warning_types(self, quest):
        from .services.quest_builder import validate_quest
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

    # ── Task 9.8: duplicate scene keys ─────────────────────────────────────────
    # Scene.key is unique at the DB level so duplicates can't exist in reality;
    # we mock the queryset to verify the validator catches the case if it ever
    # arises (e.g. after a data migration or manual DB edit).

    def test_duplicate_key_detected(self):
        from unittest.mock import patch, MagicMock
        from types import SimpleNamespace
        from .services.quest_builder import validate_quest

        quest = self._make_quest(key='qbv__quest3')
        entry = self._make_scene(quest, 'qbv__dupkey_a')
        quest.entrance_scene = entry
        quest.save()

        fake_a = SimpleNamespace(id=1, key='shared_key', title='A', scene_type='normal', requires_roll=False)
        fake_b = SimpleNamespace(id=2, key='shared_key', title='B', scene_type='normal', requires_roll=False)

        with patch('game.services.quest_builder.Quest') as MockQuest, \
             patch('game.services.quest_builder.Choice') as MockChoice, \
             patch('game.services.quest_builder.CombatEncounter') as MockCE:

            mock_q = MagicMock()
            MockQuest.objects.get.return_value = mock_q
            mock_q.entrance_scene_id = None
            mock_q.is_unlocked = False
            mock_q.hub_scenes.exists.return_value = False
            mock_q.scenes.only.return_value = [fake_a, fake_b]
            MockChoice.objects.filter.return_value.only.return_value = []
            mock_ce_qs = MagicMock()
            mock_ce_qs.only.return_value = mock_ce_qs
            mock_ce_qs.values_list.return_value = []
            MockCE.objects.filter.return_value = mock_ce_qs

            types = [w['type'] for w in validate_quest(quest.pk)]

        self.assertIn('duplicate_key', types)
