from django.urls import path
from . import views

app_name = 'campaigns'

urlpatterns = [
    path('', views.campaign_list, name='campaign_list'),
    path('create/', views.campaign_create, name='campaign_create'),
    path('<int:pk>/', views.campaign_detail, name='campaign_detail'),
    path('<int:pk>/edit/', views.campaign_edit, name='campaign_edit'),
    path('<int:pk>/archive/', views.campaign_archive, name='campaign_archive'),
    path('<int:pk>/delete/', views.campaign_delete, name='campaign_delete'),
    path('<int:pk>/add-accounts/', views.campaign_add_accounts, name='campaign_add_accounts'),
    path('<int:pk>/remove-contact/<int:contact_pk>/', views.campaign_remove_contact, name='campaign_remove_contact'),
]
