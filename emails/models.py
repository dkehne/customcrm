import uuid

from django.conf import settings
from django.db import models


class UserEmailAddress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='email_addresses', verbose_name='Benutzer',
    )
    email = models.EmailField(verbose_name='E-Mail-Adresse')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Benutzer-E-Mail-Adresse'
        verbose_name_plural = 'Benutzer-E-Mail-Adressen'
        unique_together = ('user', 'email')

    def __str__(self):
        return self.email


class UserInboundAddress(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='inbound_address', verbose_name='Benutzer',
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Eingangs-Adresse'
        verbose_name_plural = 'Eingangs-Adressen'

    @property
    def address(self):
        domain = getattr(settings, 'INBOUND_EMAIL_DOMAIN', 'example.com')
        return f'crm+{self.token}@{domain}'

    def __str__(self):
        return self.address


class InboundEmail(models.Model):
    STATUS_CHOICES = [
        ('resolved', 'Aufgelöst'),
        ('unresolved', 'Nicht aufgelöst'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='inbound_emails', verbose_name='CRM-Benutzer',
    )
    account = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='inbound_emails',
        verbose_name='Account',
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='unresolved',
        verbose_name='Status',
    )
    message_id = models.CharField(
        max_length=500, unique=True, verbose_name='Message-ID',
    )
    sender_email = models.EmailField(verbose_name='Absender')
    recipient_emails = models.TextField(
        blank=True, default='', verbose_name='Empfänger',
    )
    subject = models.CharField(max_length=500, blank=True, default='', verbose_name='Betreff')
    body_text = models.TextField(blank=True, default='', verbose_name='Text-Body')
    body_html = models.TextField(blank=True, default='', verbose_name='HTML-Body')
    eml_file = models.FileField(
        upload_to='inbound_emails/%Y/%m/', blank=True,
        verbose_name='Original .eml',
    )
    received_at = models.DateTimeField(verbose_name='Empfangen am')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Eingehende E-Mail'
        verbose_name_plural = 'Eingehende E-Mails'
        ordering = ['-received_at']

    def __str__(self):
        return self.subject or self.message_id


class EmailAttachment(models.Model):
    inbound_email = models.ForeignKey(
        InboundEmail, on_delete=models.CASCADE,
        related_name='attachments', verbose_name='E-Mail',
    )
    file = models.FileField(
        upload_to='email_attachments/%Y/%m/', verbose_name='Datei',
    )
    filename = models.CharField(max_length=300, verbose_name='Dateiname')
    content_type = models.CharField(max_length=200, verbose_name='MIME-Typ')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'E-Mail-Anhang'
        verbose_name_plural = 'E-Mail-Anhänge'

    def __str__(self):
        return self.filename
