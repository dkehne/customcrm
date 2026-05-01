import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserEmailAddress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='email_addresses', verbose_name=_('Benutzer'),
    )
    email = models.EmailField(verbose_name=_('E-Mail-Adresse'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Benutzer-E-Mail-Adresse')
        verbose_name_plural = _('Benutzer-E-Mail-Adressen')
        unique_together = ('user', 'email')

    def __str__(self):
        return self.email


class UserInboundAddress(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='inbound_address', verbose_name=_('Benutzer'),
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Eingangs-Adresse')
        verbose_name_plural = _('Eingangs-Adressen')

    @property
    def address(self):
        domain = getattr(settings, 'INBOUND_EMAIL_DOMAIN', 'example.com')
        return f'crm+{self.token}@{domain}'

    def __str__(self):
        return self.address


class InboundEmail(models.Model):
    STATUS_CHOICES = [
        ('resolved', _('Aufgelöst')),
        ('unresolved', _('Nicht aufgelöst')),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='inbound_emails', verbose_name=_('CRM-Benutzer'),
    )
    account = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='inbound_emails',
        verbose_name=_('Account'),
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='unresolved',
        verbose_name=_('Status'),
    )
    message_id = models.CharField(
        max_length=500, unique=True, verbose_name=_('Message-ID'),
    )
    sender_email = models.EmailField(verbose_name=_('Absender'))
    recipient_emails = models.TextField(
        blank=True, default='', verbose_name=_('Empfänger'),
    )
    subject = models.CharField(max_length=500, blank=True, default='', verbose_name=_('Betreff'))
    body_text = models.TextField(blank=True, default='', verbose_name=_('Text-Body'))
    body_html = models.TextField(blank=True, default='', verbose_name=_('HTML-Body'))
    eml_file = models.FileField(
        upload_to='inbound_emails/%Y/%m/', blank=True,
        verbose_name=_('Original .eml'),
    )
    received_at = models.DateTimeField(verbose_name=_('Empfangen am'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Eingehende E-Mail')
        verbose_name_plural = _('Eingehende E-Mails')
        ordering = ['-received_at']

    def __str__(self):
        return self.subject or self.message_id


class EmailAttachment(models.Model):
    inbound_email = models.ForeignKey(
        InboundEmail, on_delete=models.CASCADE,
        related_name='attachments', verbose_name=_('E-Mail'),
    )
    file = models.FileField(
        upload_to='email_attachments/%Y/%m/', verbose_name=_('Datei'),
    )
    filename = models.CharField(max_length=300, verbose_name=_('Dateiname'))
    content_type = models.CharField(max_length=200, verbose_name=_('MIME-Typ'))
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('E-Mail-Anhang')
        verbose_name_plural = _('E-Mail-Anhänge')

    def __str__(self):
        return self.filename
