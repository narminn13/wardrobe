from django.contrib import admin

from .models import Outfit, OutfitItem, WeeklyPlan


class OutfitItemInline(admin.TabularInline):
    model = OutfitItem
    extra = 0


@admin.register(WeeklyPlan)
class WeeklyPlanAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "week_start",
        "city",
        "status",
        "created_at",
    ]

    list_filter = [
        "status",
        "week_start",
    ]

    search_fields = [
        "user__email",
        "city",
    ]


@admin.register(Outfit)
class OutfitAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "weekly_plan",
        "date",
        "generated_by_ai",
    ]

    list_filter = [
        "generated_by_ai",
        "date",
    ]

    inlines = [
        OutfitItemInline
    ]


@admin.register(OutfitItem)
class OutfitItemAdmin(admin.ModelAdmin):
    list_display = [
        "outfit",
        "garment",
        "role",
        "order",
    ]