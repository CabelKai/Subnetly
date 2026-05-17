from django.contrib import admin

from .models import Application, Assignment, IPAssignment, Pool


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    list_display = ("name", "cidr", "ip_version")
    search_fields = ("name", "cidr")
    readonly_fields = ("ip_version",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


class IPAssignmentInline(admin.TabularInline):
    model = IPAssignment
    extra = 0
    autocomplete_fields = ("application",)
    fields = ("address", "application", "is_gateway", "label", "notes")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("cidr", "pool", "applications_list")
    list_filter = ("pool",)
    search_fields = ("cidr", "notes")
    autocomplete_fields = ("pool",)
    filter_horizontal = ("applications",)
    inlines = [IPAssignmentInline]

    @admin.display(description="Anwendungen")
    def applications_list(self, obj):
        return ", ".join(sorted(a.name for a in obj.applications.all()))


@admin.register(IPAssignment)
class IPAssignmentAdmin(admin.ModelAdmin):
    list_display = ("address", "assignment", "application", "is_gateway")
    list_filter = ("is_gateway",)
    search_fields = ("address", "label")
    autocomplete_fields = ("application", "assignment")
