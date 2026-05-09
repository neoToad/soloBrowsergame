from django.urls import path
from . import views

urlpatterns = [
    path('', views.root_redirect, name='root_redirect'),
    path('game/', views.game_hub, name='game_hub'),
    path('game/scene/<slug:scene_key>/', views.scene_detail, name='scene_detail'),
    path('game/choose/<int:choice_id>/', views.choice_resolve, name='choice_resolve'),
    path('game/session/restart/', views.session_restart, name='session_restart'),
    path('game/combat/attack/', views.combat_attack, name='combat_attack'),
    path('game/combat/enemy-resolve/', views.combat_resolve_enemy, name='combat_resolve_enemy'),
    path('game/combat/continue/', views.combat_continue, name='combat_continue'),
    path('game/level-up/', views.level_up, name='level_up'),
    path('game/item/use/<int:item_id>/', views.use_item, name='use_item'),
    path('game/quest/<slug:quest_key>/start/', views.start_quest, name='start_quest'),
]
