from django.test import TestCase

from game.models import PlayerContext, Requirement, RequirementGroup


class RequirementEvaluationTest(TestCase):
    def test_numeric_gte_conditions(self):
        from types import SimpleNamespace

        cases = [
            ("stat_gte", "strength", 10, SimpleNamespace(strength=10, level=5), True),
            ("stat_gte", "strength", 11, SimpleNamespace(strength=10, level=5), False),
            ("level_gte", None, 5, SimpleNamespace(level=5), True),
            ("level_gte", None, 6, SimpleNamespace(level=5), False),
        ]
        for condition_type, stat_name, stat_value, stats, expected in cases:
            with self.subTest(condition_type=condition_type, stat_value=stat_value):
                ctx = PlayerContext(stats=stats, inventory={}, completed_map={})
                req = Requirement(
                    condition_type=condition_type, stat_name=stat_name, stat_value=stat_value
                )
                self.assertEqual(req.evaluate(ctx), expected)

    def test_has_item_missing_item(self):
        req_has = Requirement(condition_type="has_item", required_item_id=1)
        req_missing = Requirement(condition_type="missing_item", required_item_id=1)

        inventory = {1: "some_item_instance"}
        ctx = PlayerContext(stats=None, inventory=inventory, completed_map={})
        self.assertTrue(req_has.evaluate(ctx))
        self.assertFalse(req_missing.evaluate(ctx))

        inventory = {2: "other_item"}
        ctx.inventory = inventory
        self.assertFalse(req_has.evaluate(ctx))
        self.assertTrue(req_missing.evaluate(ctx))

    def test_quest_completed_not_done(self):
        req_done = Requirement(condition_type="quest_completed", required_quest_id=1)
        req_not_done = Requirement(condition_type="quest_not_done", required_quest_id=1)

        completed_map = {1: "victory"}
        ctx = PlayerContext(stats=None, inventory={}, completed_map=completed_map)
        self.assertTrue(req_done.evaluate(ctx))
        self.assertFalse(req_not_done.evaluate(ctx))

        completed_map = {2: "victory"}
        ctx.completed_map = completed_map
        self.assertFalse(req_done.evaluate(ctx))
        self.assertTrue(req_not_done.evaluate(ctx))

    def test_quest_ending(self):
        req = Requirement(
            condition_type="quest_ending", required_quest_id=1, required_ending_type="victory"
        )

        ctx = PlayerContext(stats=None, inventory={}, completed_map={1: "victory"})
        self.assertTrue(req.evaluate(ctx))
        ctx.completed_map = {1: "defeat"}
        self.assertFalse(req.evaluate(ctx))
        ctx.completed_map = {2: "victory"}
        self.assertFalse(req.evaluate(ctx))

    def test_requirement_group_logic(self):
        r1 = Requirement.objects.create(condition_type="stat_gte", stat_name="strength", stat_value=10)
        r2 = Requirement.objects.create(condition_type="stat_gte", stat_name="agility", stat_value=10)

        group_all = RequirementGroup.objects.create(label="All", logic="all")
        group_all.requirements.add(r1, r2)

        group_any = RequirementGroup.objects.create(label="Any", logic="any")
        group_any.requirements.add(r1, r2)

        from types import SimpleNamespace

        stats_both = SimpleNamespace(strength=10, agility=10)
        stats_one = SimpleNamespace(strength=10, agility=5)
        stats_none = SimpleNamespace(strength=5, agility=5)

        self.assertTrue(group_all.evaluate(PlayerContext(stats_both, {}, {})))
        self.assertFalse(group_all.evaluate(PlayerContext(stats_one, {}, {})))

        self.assertTrue(group_any.evaluate(PlayerContext(stats_one, {}, {})))
        self.assertFalse(group_any.evaluate(PlayerContext(stats_none, {}, {})))

        group_empty = RequirementGroup.objects.create(label="Empty", logic="all")
        self.assertTrue(group_empty.evaluate(PlayerContext(stats_none, {}, {})))
