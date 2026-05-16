from django.contrib import admin

from .models import Assignment, Customer, Pool


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    list_display = ("name", "cidr", "ip_version", "block_prefix")
    search_fields = ("name", "cidr")
    readonly_fields = ("ip_version",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("cidr", "pool", "customer", "gateway")
    list_filter = ("pool", "customer")
    search_fields = ("cidr", "notes", "customer__name")
    autocomplete_fields = ("pool", "customer")
