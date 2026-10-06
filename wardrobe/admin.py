from django.contrib import admin

from .models import Garment, GarmentAnalysis


@admin.register(Garment)
class GarmentAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "user",
        "category",
        "formality",
        "status",
        "ai_analyzed",
        "created_at",
    ]

    list_filter = [
        "category",
        "formality",
        "status",
        "ai_analyzed",
    ]

    search_fields = [
        "name",
        "user__email",
        "color",
        "material",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
        "ai_confidence",
        "ai_analyzed",
    ]


@admin.register(GarmentAnalysis)
class GarmentAnalysisAdmin(admin.ModelAdmin):
    list_display = [
        "garment",
        "model_name",
        "analyzed_at",
    ]

    readonly_fields = [
        "raw_response",
        "model_name",
        "analyzed_at",
    ]