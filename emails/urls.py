from django.urls import path

from . import views

app_name = 'emails'

urlpatterns = [
    path('', views.profile_overview, name='profile_overview'),
    path('email-adressen/add/', views.email_address_add, name='email_address_add'),
    path('email-adressen/<int:pk>/delete/', views.email_address_delete, name='email_address_delete'),
    path('emails/', views.unresolved_emails, name='unresolved_emails'),
    path('emails/<int:pk>/assign/', views.assign_email, name='assign_email'),
    path('emails/<int:pk>/delete/', views.delete_email, name='delete_email'),
    path('set-default-product/', views.set_default_product, name='set_default_product'),
]
