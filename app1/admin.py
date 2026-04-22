# ADMINPANEL\server\app1\admin.py
from django.contrib import admin
from .models import UploadedName


@admin.register(UploadedName)
class UploadedNameAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'data_type', 'timestamp', 'received')
    list_filter = ('data_type', 'received', 'timestamp')
    search_fields = ('name', 'content')
    readonly_fields = ('timestamp',)
    list_per_page = 20
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'data_type', 'received')
        }),
        ('Content', {
            'fields': ('content',),
            'classes': ('wide',)
        }),
        ('Metadata', {
            'fields': ('timestamp',),
            'classes': ('collapse',)
        }),
    )