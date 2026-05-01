from unittest.mock import patch

from django.test import Client, TestCase

from game.models import GameSession, Scene

from game.tests.factories import bootstrap_game_session


class RivalContestTest(TestCase):
    fixtures = [
        "game/fixtures/arc.json",
        "game/fixtures/property.json",
        "game/fixtures/requirement.json",
        "game/fixtures/requirementgroup.json",
        "game/fixtures/scene.json",
        "game/fixtures/choice.json",
        "game/fixtures/quest.json",
    ]

    def setUp(self):
        self.client = Client()
        self.client.get("/game/")
        self.session = GameSession.objects.first()

    def test_process_turn_income_skips_save_when_no_logs(self):
        from game.services.property_service import process_turn_income

        with patch.object(self.session.stats, "save") as stats_save:
            logs, totals = process_turn_income(self.session)

        self.assertEqual(logs, [])
        self.assertEqual(totals, {"cash": 0, "heat": 0, "rep": 0})
        stats_save.assert_not_called()

    def test_trigger_rival_contest_returns_none_without_contestable_properties(self):
        from game.services.property_service import trigger_rival_contest

        self.session.stats.heat = 200
        self.session.stats.save()
        with patch("game.services.property_service.random.random", return_value=0):
            log, unlocked = trigger_rival_contest(self.session)

        self.assertIsNone(log)
        self.assertIsNone(unlocked)

    def test_trigger_rival_contest_materializes_queryset_once(self):
        from game.models import PlayerProperty, Property, RivalClaim
        from game.services.property_service import trigger_rival_contest

        start_scene = Scene.objects.create(
            key="phase4__contest_start", title="Phase4 Start", body="start", scene_type="normal"
        )
        resolution_scene = Scene.objects.create(
            key="phase4__contest_resolution",
            title="Phase4 Resolution",
            body="resolve",
            scene_type="normal",
        )
        self.session.current_scene = start_scene
        self.session.save(update_fields=["current_scene"])
        self.session.stats.heat = 200
        self.session.stats.save()

        prop = Property.objects.create(
            key="phase4_property",
            name="Phase4 Property",
            property_type="business",
            cash_per_turn=5,
            heat_per_turn=1,
            rep_per_turn=1,
            is_contestable=True,
            resolution_scene=resolution_scene,
        )
        player_property = PlayerProperty.objects.create(
            session=self.session, property=prop, is_contested=False
        )

        with patch("game.services.property_service.random.random", return_value=0), patch(
            "game.services.property_service.random.choice", side_effect=lambda seq: seq[0]
        ) as mock_choice:
            log, unlocked = trigger_rival_contest(self.session)

        self.assertIsNotNone(log)
        self.assertEqual(unlocked, resolution_scene)
        self.assertTrue(PlayerProperty.objects.filter(pk=player_property.pk, is_contested=True).exists())
        self.assertTrue(
            RivalClaim.objects.filter(player_property=player_property, resolution_scene=resolution_scene).exists()
        )
        self.assertEqual(mock_choice.call_count, 1)
        self.assertIsInstance(mock_choice.call_args.args[0], list)

    def test_resolve_contest_victory_clears_claim_and_contested_flag(self):
        from game.models import PlayerProperty, Property, RivalClaim
        from game.services.property_service import resolve_contest

        resolution_scene = Scene.objects.create(
            key="phase6__contest_victory_resolution",
            title="Victory Resolution",
            body="resolve",
            scene_type="ending",
            ending_type="victory",
        )
        prop = Property.objects.create(
            key="phase6_victory_property",
            name="Phase6 Victory Property",
            property_type="business",
            cash_per_turn=2,
            is_contestable=True,
            resolution_scene=resolution_scene,
        )
        player_property = PlayerProperty.objects.create(
            session=self.session, property=prop, is_contested=True
        )
        claim = RivalClaim.objects.create(player_property=player_property, resolution_scene=resolution_scene)

        log = resolve_contest(self.session, claim, "victory")

        player_property.refresh_from_db()
        self.assertFalse(player_property.is_contested)
        self.assertFalse(RivalClaim.objects.filter(pk=claim.pk).exists())
        self.assertIn("is yours again", log)

    def test_resolve_contest_non_victory_removes_property_and_claim(self):
        from game.models import PlayerProperty, Property, RivalClaim
        from game.services.property_service import resolve_contest

        resolution_scene = Scene.objects.create(
            key="phase6__contest_defeat_resolution",
            title="Defeat Resolution",
            body="resolve",
            scene_type="ending",
            ending_type="defeat",
        )
        prop = Property.objects.create(
            key="phase6_defeat_property",
            name="Phase6 Defeat Property",
            property_type="business",
            cash_per_turn=2,
            is_contestable=True,
            resolution_scene=resolution_scene,
        )
        player_property = PlayerProperty.objects.create(
            session=self.session, property=prop, is_contested=True
        )
        claim = RivalClaim.objects.create(player_property=player_property, resolution_scene=resolution_scene)

        log = resolve_contest(self.session, claim, "defeat")

        self.assertFalse(PlayerProperty.objects.filter(pk=player_property.pk).exists())
        self.assertFalse(RivalClaim.objects.filter(pk=claim.pk).exists())
        self.assertIn("is gone", log)


class PropertyServiceTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = bootstrap_game_session(self.client)
        self.stats = self.session.stats

    def test_apply_property_rewards_grants_property_on_arrival(self):
        from game.models.property import PlayerProperty, Property
        from game.services.property_service import apply_property_rewards

        prop = Property.objects.create(key="test_bar", name="Test Bar", property_type="business")
        scene = Scene.objects.create(
            key="prop__receive", title="Receive", body="", scene_type="normal", receive_property=prop
        )

        logs = apply_property_rewards(self.session, scene)

        self.assertTrue(PlayerProperty.objects.filter(session=self.session, property=prop).exists())
        self.assertEqual(len(logs), 1)
        self.assertIn("Test Bar", logs[0])

    def test_apply_property_rewards_skips_already_owned_property(self):
        from game.models.property import PlayerProperty, Property
        from game.services.property_service import apply_property_rewards

        prop = Property.objects.create(key="owned_bar", name="Owned Bar", property_type="business")
        PlayerProperty.objects.create(session=self.session, property=prop)
        scene = Scene.objects.create(
            key="prop__receive2", title="Receive2", body="", scene_type="normal", receive_property=prop
        )

        apply_property_rewards(self.session, scene)

        self.assertEqual(PlayerProperty.objects.filter(session=self.session, property=prop).count(), 1)

    def test_apply_property_rewards_removes_property_on_lose(self):
        from game.models.property import PlayerProperty, Property
        from game.services.property_service import apply_property_rewards

        prop = Property.objects.create(key="lost_bar", name="Lost Bar", property_type="business")
        PlayerProperty.objects.create(session=self.session, property=prop)
        scene = Scene.objects.create(
            key="prop__lose", title="Lose", body="", scene_type="normal", lose_property=prop
        )

        logs = apply_property_rewards(self.session, scene)

        self.assertFalse(PlayerProperty.objects.filter(session=self.session, property=prop).exists())
        self.assertEqual(len(logs), 1)
        self.assertIn("Lost Bar", logs[0])

    def test_process_turn_income_with_active_properties_applies_cash_rep_heat(self):
        from game.models.property import PlayerProperty, Property
        from game.services.property_service import process_turn_income

        prop = Property.objects.create(
            key="cash_cow",
            name="Cash Cow",
            property_type="business",
            cash_per_turn=100,
            heat_per_turn=5,
            rep_per_turn=3,
        )
        PlayerProperty.objects.create(session=self.session, property=prop)
        self.stats.cash = 0
        self.stats.heat = 20
        self.stats.rep = 0
        self.stats.save()

        logs, totals = process_turn_income(self.session)

        self.stats.refresh_from_db()
        self.assertEqual(self.stats.cash, 100)
        self.assertEqual(self.stats.heat, 15)
        self.assertEqual(self.stats.rep, 3)
        self.assertGreater(len(logs), 0)
        self.assertIn("Cash Cow", logs[0])

    def test_apply_property_rewards_grants_territory_on_arrival(self):
        from game.models.property import PlayerDiscoveredTerritory, PlayerTerritory, Territory
        from game.services.property_service import apply_property_rewards

        territory = Territory.objects.create(key="riverfront", name="Riverfront", cash_per_turn=12)
        scene = Scene.objects.create(
            key="territory__receive_runtime",
            title="Receive Territory",
            body="",
            scene_type="normal",
            receive_territory=territory,
        )

        logs = apply_property_rewards(self.session, scene)

        self.assertTrue(PlayerTerritory.objects.filter(session=self.session, territory=territory).exists())
        self.assertTrue(
            PlayerDiscoveredTerritory.objects.filter(session=self.session, territory=territory).exists()
        )
        self.assertIn("Riverfront", "\n".join(logs))

    def test_process_turn_income_with_active_territories_applies_cash_rep_heat(self):
        from game.models.property import PlayerTerritory, Territory
        from game.services.property_service import process_turn_income

        territory = Territory.objects.create(
            key="iron-ward",
            name="Iron Ward",
            cash_per_turn=50,
            heat_per_turn=4,
            rep_per_turn=2,
        )
        PlayerTerritory.objects.create(session=self.session, territory=territory)
        self.stats.cash = 0
        self.stats.heat = 10
        self.stats.rep = 0
        self.stats.save()

        logs, totals = process_turn_income(self.session)

        self.stats.refresh_from_db()
        self.assertEqual(self.stats.cash, 50)
        self.assertEqual(self.stats.heat, 6)
        self.assertEqual(self.stats.rep, 2)
        self.assertEqual(totals["cash"], 50)
        self.assertEqual(totals["heat"], -4)
        self.assertEqual(totals["rep"], 2)
        self.assertIn("Iron Ward", "\n".join(logs))

    def test_process_turn_income_skips_contested_territories(self):
        from game.models.property import PlayerTerritory, Territory
        from game.services.property_service import process_turn_income

        territory = Territory.objects.create(
            key="contested-yard",
            name="Contested Yard",
            cash_per_turn=80,
            heat_per_turn=3,
            rep_per_turn=1,
        )
        PlayerTerritory.objects.create(session=self.session, territory=territory, is_contested=True)
        self.stats.cash = 5
        self.stats.heat = 10
        self.stats.rep = 2
        self.stats.save()

        logs, totals = process_turn_income(self.session)

        self.stats.refresh_from_db()
        self.assertEqual(self.stats.cash, 5)
        self.assertEqual(self.stats.heat, 10)
        self.assertEqual(self.stats.rep, 2)
        self.assertEqual(logs, [])
        self.assertEqual(totals, {"cash": 0, "heat": 0, "rep": 0})

    def test_apply_property_rewards_removes_territory_on_arrival(self):
        from game.models.property import PlayerTerritory, Territory
        from game.services.property_service import apply_property_rewards

        territory = Territory.objects.create(key="red-line", name="Red Line")
        PlayerTerritory.objects.create(session=self.session, territory=territory)
        scene = Scene.objects.create(
            key="territory__lose_runtime",
            title="Lose Territory",
            body="",
            scene_type="normal",
            lose_territory=territory,
        )

        logs = apply_property_rewards(self.session, scene)

        self.assertFalse(PlayerTerritory.objects.filter(session=self.session, territory=territory).exists())
        self.assertIn("Red Line", "\n".join(logs))


class ArrivalServiceTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = bootstrap_game_session(self.client)
        self.stats = self.session.stats

    def test_process_arrival_on_quest_ending_triggers_income_and_turn_summary(self):
        from game.models import Quest
        from game.services.arrival import process_arrival

        quest = Quest.objects.create(key="arr__quest", title="Arrival Quest", description="")
        ending_scene = Scene.objects.create(
            quest=quest,
            key="arr__ending",
            title="Ending",
            body="",
            scene_type="ending",
            ending_type="victory",
        )

        logs, turn_summary = process_arrival(self.session, self.stats, {}, {}, ending_scene)

        self.assertIsNotNone(turn_summary)
        self.assertIn("income_totals", turn_summary)
        combined = "\n".join(logs)
        self.assertIn(quest.title, combined)

    def test_process_arrival_resolves_active_rival_claim_on_victory_scene(self):
        from game.models import Quest
        from game.models.property import PlayerProperty, Property, RivalClaim
        from game.services.arrival import process_arrival

        quest = Quest.objects.create(key="arr__quest2", title="Rival Quest", description="")
        ending_scene = Scene.objects.create(
            quest=quest,
            key="arr__victory",
            title="Victory",
            body="",
            scene_type="ending",
            ending_type="victory",
        )

        prop = Property.objects.create(
            key="contested_bar", name="Contested Bar", property_type="business"
        )
        pp = PlayerProperty.objects.create(session=self.session, property=prop, is_contested=True)
        claim = RivalClaim.objects.create(player_property=pp, resolution_scene=ending_scene)

        logs, _ = process_arrival(self.session, self.stats, {}, {}, ending_scene)

        self.assertFalse(RivalClaim.objects.filter(pk=claim.pk).exists())
        self.assertIn("Rival backed down", "\n".join(logs))

