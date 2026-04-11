from django.test import TestCase, Client
from django.urls import reverse
from .models import Scene, GameSession, PlayerStats, Choice, Quest, CompletedQuest

class GameNavigationTest(TestCase):
    fixtures = ['game/fixtures/hub.json', 'game/fixtures/quest_haunted_mine.json']

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
        self.assertContains(response, "Notice Board")
        self.assertContains(response, "Return to the main square")

    def test_stat_gated_choice(self):
        # Initialize session
        self.client.get('/game/')
        game_session = GameSession.objects.first()
        stats = game_session.stats
        
        # The Haunted Mine entrance scene
        scene = Scene.objects.get(key='mine__entrance')
        
        # Choice 5: "Sneak past the guards" requires agility 7. Default is 5.
        choice_sneak = Choice.objects.get(pk=5)
        choice_sneak.required_stat = 'agility'
        choice_sneak.required_minimum = 7
        choice_sneak.save()
        
        # Check that it's NOT visible with default agility (5)
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'mine__entrance'}))
        self.assertNotContains(response, "Sneak past the guards")
        
        # Increase agility to 7
        stats.agility = 7
        stats.save()
        
        # Check that it IS visible now
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'mine__entrance'}))
        self.assertContains(response, "Sneak past the guards")

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
        # ... original code ...
        pass

class NoticeBoardTest(TestCase):
    fixtures = ['game/fixtures/hub.json', 'game/fixtures/quest_haunted_mine.json']

    def setUp(self):
        self.client = Client()
        self.client.get('/game/')
        self.session = GameSession.objects.first()
        self.mine = Quest.objects.get(key='the_haunted_mine')
        self.mine_entrance = Scene.objects.get(key='mine__entrance')

    def test_notice_board_initial_state(self):
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'hub__notice_board'}))
        self.assertContains(response, "Available Quests")
        self.assertContains(response, self.mine.title)
        self.assertIn('quest-entry--available', response.content.decode())

    def test_quest_prerequisite_gating(self):
        # Create second quest requiring haunted mine
        second_quest = Quest.objects.create(
            key='second_quest',
            title='The Second Quest',
            description='Locked until mine is done.',
            required_quest=self.mine,
            entrance_scene=self.mine_entrance
        )
        
        # Check it's locked
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'hub__notice_board'}))
        self.assertContains(response, "Locked Quests")
        self.assertContains(response, second_quest.title)
        self.assertContains(response, f"Requires completion of: {self.mine.title}")
        
        # Complete haunted mine
        CompletedQuest.objects.create(session=self.session, quest=self.mine, ending_type='victory')
        
        # Check it's now available
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'hub__notice_board'}))
        self.assertContains(response, second_quest.title)
        # Should be in available section now, search for the title within the available block
        # (Simplified check: title exists, and it's no longer in the locked section)
        self.assertNotContains(response, f"Requires completion of: {self.mine.title}")

    def test_stat_gated_quest(self):
        # Create third quest requiring intellect 9
        intellect_quest = Quest.objects.create(
            key='intellect_quest',
            title='Intellect Quest',
            description='Requires brains.',
            required_stat='intellect',
            required_minimum=9,
            entrance_scene=self.mine_entrance
        )
        
        # Initial stats: intellect is 5
        self.session.stats.intellect = 6
        self.session.stats.save()
        
        # Check it's locked
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'hub__notice_board'}))
        self.assertContains(response, "Requires Intellect 9 (yours: 6)")
        
        # Raise intellect to 9
        self.session.stats.intellect = 9
        self.session.stats.save()
        
        # Check it's available
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'hub__notice_board'}))
        self.assertNotContains(response, "Requires Intellect 9")
        self.assertContains(response, intellect_quest.title)

    def test_completed_quest_rendering(self):
        # Complete mine
        cq = CompletedQuest.objects.create(session=self.session, quest=self.mine, ending_type='victory')
        
        response = self.client.get(reverse('scene_detail', kwargs={'scene_key': 'hub__notice_board'}))
        self.assertContains(response, "Completed Quests")
        self.assertContains(response, self.mine.title)
        self.assertContains(response, "Victory")
        self.assertContains(response, cq.completed_at.strftime("%b %d, %Y"))
        self.assertContains(response, "Play again")

    def test_start_quest_view(self):
        # Try to start locked quest (by stat)
        locked_quest = Quest.objects.create(
            key='locked_quest',
            title='Locked Quest',
            description='Requires brains.',
            required_stat='intellect',
            required_minimum=99,
            entrance_scene=self.mine_entrance
        )
        response = self.client.post(reverse('start_quest', kwargs={'quest_key': 'locked_quest'}))
        self.assertEqual(response.status_code, 403)
        
        # Start available quest
        response = self.client.post(reverse('start_quest', kwargs={'quest_key': 'the_haunted_mine'}))
        self.assertRedirects(response, reverse('scene_detail', kwargs={'scene_key': self.mine_entrance.key}))
        
        # Check session advanced
        self.session.refresh_from_db()
        self.assertEqual(self.session.current_scene, self.mine_entrance)
        
        # Check log
        self.assertTrue(self.session.log.filter(text__icontains="accepted the quest").exists())

    def test_start_quest_htmx(self):
        response = self.client.post(
            reverse('start_quest', kwargs={'quest_key': 'the_haunted_mine'}),
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="scene-panel"', response.content.decode())
        self.assertContains(response, self.mine_entrance.title)

