from django.test import TestCase, Client
from django.urls import reverse
from .models import Scene, GameSession, PlayerStats, Choice

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
