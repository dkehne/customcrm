from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.account_list, name='account_list'),
    path('to-campaign/', views.accounts_to_campaign, name='accounts_to_campaign'),
    path('search/', views.account_search, name='account_search'),
    path('create/', views.account_create, name='account_create'),
    path('<int:pk>/', views.account_detail, name='account_detail'),
    path('<int:pk>/edit/', views.account_edit, name='account_edit'),
    path('<int:pk>/archive/', views.account_archive, name='account_archive'),
    path('<int:pk>/delete/', views.account_delete, name='account_delete'),
    path('<int:pk>/assign/', views.account_assign_owner, name='account_assign_owner'),
    # Contacts
    path('contacts/', views.contact_list, name='contact_list'),
    path('<int:account_pk>/contacts/add/', views.contact_add, name='contact_add'),
    path('contacts/<int:pk>/edit/', views.contact_edit, name='contact_edit'),
    path('contacts/<int:pk>/archive/', views.contact_archive, name='contact_archive'),
    path('contacts/<int:pk>/delete/', views.contact_delete, name='contact_delete'),
    # Account Products
    path('<int:account_pk>/products/add/', views.account_product_add, name='account_product_add'),
    path('account-products/<int:pk>/edit/', views.account_product_edit, name='account_product_edit'),
    path('account-products/<int:pk>/archive/', views.account_product_archive, name='account_product_archive'),
    path('account-products/<int:pk>/delete/', views.account_product_delete, name='account_product_delete'),
    # Contracts
    path('<int:account_pk>/contracts/add/', views.contract_add, name='contract_add'),
    path('contracts/<int:pk>/edit/', views.contract_edit, name='contract_edit'),
    path('contracts/<int:pk>/archive/', views.contract_archive, name='contract_archive'),
    path('contracts/<int:pk>/delete/', views.contract_delete, name='contract_delete'),
    path('contract-documents/<int:pk>/delete/', views.contract_document_delete, name='contract_document_delete'),
    # Activities
    path('<int:account_pk>/activities/add/', views.activity_add, name='activity_add'),
    path('activities/<int:pk>/delete/', views.activity_delete, name='activity_delete'),
    # Todos
    path('<int:account_pk>/todos/add/', views.todo_add, name='todo_add'),
    path('todos/<int:pk>/edit/', views.todo_edit, name='todo_edit'),
    path('todos/<int:pk>/complete/', views.todo_complete, name='todo_complete'),
    path('todos/<int:pk>/delete/', views.todo_delete, name='todo_delete'),
    # Account Campaigns
    path('<int:account_pk>/campaigns/add/', views.account_campaign_add, name='account_campaign_add'),
    path('account-campaigns/<int:pk>/edit/', views.account_campaign_edit, name='account_campaign_edit'),
    path('account-campaigns/<int:pk>/toggle/', views.account_campaign_toggle_success, name='account_campaign_toggle_success'),
    path('account-campaigns/<int:pk>/delete/', views.account_campaign_delete, name='account_campaign_delete'),
]
