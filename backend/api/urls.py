from django.urls import path
from . import views

urlpatterns = [
    path('hello/', views.get_dashboard_stats, name='hello'),
    path('stats/', views.get_dashboard_stats, name='stats'),
    path('incidents/', views.get_incidents, name='incidents'),
    path('sectors/', views.get_sectors, name='sectors'),
    path('types/', views.get_types, name='types'),
    path('sector-report/<str:secteur>/', views.get_sector_report, name='sector-report'),
    path('chat/', views.chat, name='chat'),
    
    path('chat-stream/', views.chat_stream, name='chat-stream'),
    path('chat-test/', views.chat_test, name='chat-test'),
    path('status/', views.status, name='status'),
]