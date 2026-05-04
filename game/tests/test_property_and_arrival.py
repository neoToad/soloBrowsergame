from django.test import Client, TestCase

from game.models import Scene

from game.tests.factories import bootstrap_game_session


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

    def test_process_turn_income_with_no_properties_or_territories_returns_zeroes(self):
        from game.services.property_service import process_turn_income

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


