from django.contrib import admin

from .models import UserEmailAddress, UserInboundAddress, InboundEmail, EmailAttachment


@admin.register(UserEmailAddress)
class UserEmailAddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'email', 'created_at')


@admin.register(UserInboundAddress)
class UserInboundAddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'address', 'created_at')


class EmailAttachmentInline(admin.TabularInline):
    model = EmailAttachment
    extra = 0


@admin.register(InboundEmail)
class InboundEmailAdmin(admin.ModelAdmin):
    list_display = ('subject', 'sender_email', 'user', 'account', 'status', 'received_at')
    list_filter = ('status',)
    inlines = [EmailAttachmentInline]
