from django.test import SimpleTestCase
from django.urls import resolve, reverse

from game import views


class RouteResolutionTest(SimpleTestCase):
    def test_named_routes_resolve_to_public_view_callables(self):
        cases = [
            ("root_redirect", {}, views.root_redirect),
            ("game_hub", {}, views.game_hub),
            ("scene_detail", {"scene_key": "hub__apartment"}, views.scene_detail),
            ("choice_resolve", {"choice_id": 1}, views.choice_resolve),
            ("combat_attack", {}, views.combat_attack),
            ("combat_resolve_enemy", {}, views.combat_resolve_enemy),
            ("combat_continue", {}, views.combat_continue),
            ("level_up", {}, views.level_up),
            ("use_item", {"item_id": 1}, views.use_item),
            ("start_quest", {"quest_key": "q1"}, views.start_quest),
        ]

        for route_name, kwargs, expected in cases:
            with self.subTest(route_name=route_name):
                match = resolve(reverse(route_name, kwargs=kwargs))
                self.assertIs(match.func, expected)
