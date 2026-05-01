from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.app_urls')),
    path('accounts/', include('accounts.urls')),
    path('products/', include('products.urls')),
    path('contracts/', include('contracts.urls')),
    path('campaigns/', include('campaigns.urls')),
    path('profil/', include('emails.urls')),
    path('settings/', include('core.settings_urls')),
]

if getattr(settings, 'OIDC_ENABLED', False):
    urlpatterns += [path('oidc/', include('mozilla_django_oidc.urls'))]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
