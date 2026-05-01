from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('aufgaben/', views.todo_list, name='todo_list'),
    path('pipeline/', views.pipeline, name='pipeline'),
    path('meine-kunden/', views.my_accounts, name='my_accounts'),
    path('passwort/', views.password_change, name='password_change'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('media/<path:path>', views.protected_media, name='protected_media'),
    path('analyse/', views.analyse, name='analyse'),
]
