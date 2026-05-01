from django.urls import path
from . import settings_views as views

app_name = 'settings'

urlpatterns = [
    # Site Settings (Branding)
    path('branding/', views.site_settings, name='site_settings'),
    # Account Types
    path('account-types/', views.account_type_list, name='account_type_list'),
    path('account-types/create/', views.account_type_create, name='account_type_create'),
    path('account-types/<int:pk>/edit/', views.account_type_edit, name='account_type_edit'),
    path('account-types/<int:pk>/archive/', views.account_type_archive, name='account_type_archive'),
    path('account-types/<int:pk>/delete/', views.account_type_delete, name='account_type_delete'),
    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/create/', views.product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/archive/', views.product_archive, name='product_archive'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    # Product Phases
    path('products/<int:product_pk>/phases/create/', views.product_phase_create, name='product_phase_create'),
    path('phases/<int:pk>/edit/', views.product_phase_edit, name='product_phase_edit'),
    path('phases/<int:pk>/delete/', views.product_phase_delete, name='product_phase_delete'),
    # Product Fields
    path('products/<int:product_pk>/fields/create/', views.product_field_create, name='product_field_create'),
    path('fields/<int:pk>/edit/', views.product_field_edit, name='product_field_edit'),
    path('fields/<int:pk>/archive/', views.product_field_archive, name='product_field_archive'),
    path('fields/<int:pk>/delete/', views.product_field_delete, name='product_field_delete'),
    # Contract Types
    path('contract-types/', views.contract_type_list, name='contract_type_list'),
    path('contract-types/create/', views.contract_type_create, name='contract_type_create'),
    path('contract-types/<int:pk>/edit/', views.contract_type_edit, name='contract_type_edit'),
    path('contract-types/<int:pk>/archive/', views.contract_type_archive, name='contract_type_archive'),
    path('contract-types/<int:pk>/toggle-active/', views.contract_type_toggle_active, name='contract_type_toggle_active'),
    path('contract-types/<int:pk>/delete/', views.contract_type_delete, name='contract_type_delete'),
    # Users
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
]
