from django.contrib import admin

from .models import Application, Assignment, Pool


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    list_display = ("name", "cidr", "ip_version", "block_prefix")
    search_fields = ("name", "cidr")
    readonly_fields = ("ip_version",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("cidr", "pool", "application", "gateway")
    list_filter = ("pool", "application")
    search_fields = ("cidr", "notes", "application__name")
    autocomplete_fields = ("pool", "application")
