from django.shortcuts import redirect
from django.urls import path
from . import views

urlpatterns = [
    path('', lambda r: redirect('/game/')),
    path('game/', views.game_hub, name='game_hub'),
    path('game/scene/<slug:scene_key>/', views.scene_detail, name='scene_detail'),
    path('game/choose/<int:choice_id>/', views.choice_resolve, name='choice_resolve'),
    path('game/combat/attack/', views.combat_attack, name='combat_attack'),
    path('game/combat/enemy-resolve/', views.combat_resolve_enemy, name='combat_resolve_enemy'),
    path('game/combat/continue/', views.combat_continue, name='combat_continue'),
    path('game/level-up/', views.level_up, name='level_up'),
    path('game/item/use/<int:item_id>/', views.use_item, name='use_item'),
    path('game/quest/<slug:quest_key>/start/', views.start_quest, name='start_quest'),
    path('game/jobs/recon/<slug:job_key>/', views.job_recon_start, name='job_recon_start'),
    path('game/jobs/recon/<slug:job_key>/commit/', views.job_recon_commit, name='job_recon_commit'),
    path('game/jobs/recon/<slug:job_key>/walk-away/', views.job_recon_walk_away, name='job_recon_walk_away'),
    path('game/jobs/contact/<int:offer_id>/start/', views.job_contact_start, name='job_contact_start'),
    path('game/jobs/run/<int:run_id>/beat1/', views.job_run_beat_1, name='job_run_beat_1'),
    path('game/jobs/run/<int:run_id>/beat2/', views.job_run_beat_2, name='job_run_beat_2'),
    path('game/jobs/run/<int:run_id>/abort/', views.job_run_abort, name='job_run_abort'),
    path('game/jobs/run/<int:run_id>/resolve/', views.job_run_resolve, name='job_run_resolve'),
]
