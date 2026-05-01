from django.contrib import admin

from .models import RegionHealthUpload, RegionHealthEntry


class RegionHealthEntryInline(admin.TabularInline):
    model = RegionHealthEntry
    extra = 0
    readonly_fields = ('region_name', 'account', 'ampel_color', 'ampel_score')
    fields = ('region_name', 'account', 'ampel_color', 'ampel_score')
    can_delete = False


@admin.register(RegionHealthUpload)
class RegionHealthUploadAdmin(admin.ModelAdmin):
    list_display = ('filename', 'uploaded_at', 'uploaded_by', 'rows_total', 'rows_matched')
    inlines = [RegionHealthEntryInline]


@admin.register(RegionHealthEntry)
class RegionHealthEntryAdmin(admin.ModelAdmin):
    list_display = ('region_name', 'account', 'ampel_color', 'ampel_score', 'upload')
    list_filter = ('ampel_color', 'upload')
    search_fields = ('region_name', 'account__name')
    raw_id_fields = ('account',)
