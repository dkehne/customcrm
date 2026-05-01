"""Context processors for site-wide template variables."""

from importlib.metadata import version

from emails.models import InboundEmail

from .models import SiteSettings


def site_branding(request):
    """Add site branding settings to all templates."""
    settings = SiteSettings.get_settings()
    return {
        'site_settings': settings,
        'site_name': settings.site_name,
        'site_logo': settings.logo,
        'primary_color': settings.primary_color,
    }


def app_version(request):
    """Add application version to all templates."""
    return {
        'app_version': version('customcrm'),
    }


def unresolved_email_count(request):
    """Add unresolved inbound email count for the current user."""
    if not request.user.is_authenticated:
        return {}
    count = InboundEmail.objects.filter(user=request.user, status='unresolved').count()
    return {'unresolved_email_count': count}
