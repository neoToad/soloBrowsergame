from django.shortcuts import redirect
from django.urls import path
from . import views

urlpatterns = [
    path('', lambda r: redirect('/game/')),
    path('game/', views.game_hub, name='game_hub'),
    path('game/scene/<slug:scene_key>/', views.scene_detail, name='scene_detail'),
]
