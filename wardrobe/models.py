import uuid

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models


def garment_image_path(instance, filename):
    extension = filename.split(".")[-1].lower()

    return (
        f"users/{instance.user_id}/garments/"
        f"{uuid.uuid4().hex}.{extension}"
    )


class Garment(models.Model):
    CATEGORY_TOP = "top"
    CATEGORY_BOTTOM = "bottom"
    CATEGORY_DRESS = "dress"
    CATEGORY_OUTERWEAR = "outerwear"
    CATEGORY_SHOES = "shoes"
    CATEGORY_ACCESSORY = "accessory"
    CATEGORY_OTHER = "other"

    CATEGORY_CHOICES = [
        (CATEGORY_TOP, "Top"),
        (CATEGORY_BOTTOM, "Bottom"),
        (CATEGORY_DRESS, "Dress"),
        (CATEGORY_OUTERWEAR, "Outerwear"),
        (CATEGORY_SHOES, "Shoes"),
        (CATEGORY_ACCESSORY, "Accessory"),
        (CATEGORY_OTHER, "Other"),
    ]

    STATUS_AVAILABLE = "available"
    STATUS_UNAVAILABLE = "unavailable"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = [
        (STATUS_AVAILABLE, "Available"),
        (STATUS_UNAVAILABLE, "Unavailable"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    FORMALITY_CASUAL = "casual"
    FORMALITY_SMART_CASUAL = "smart_casual"
    FORMALITY_FORMAL = "formal"
    FORMALITY_SPORT = "sport"
    FORMALITY_OTHER = "other"

    FORMALITY_CHOICES = [
        (FORMALITY_CASUAL, "Casual"),
        (FORMALITY_SMART_CASUAL, "Smart casual"),
        (FORMALITY_FORMAL, "Formal"),
        (FORMALITY_SPORT, "Sport"),
        (FORMALITY_OTHER, "Other"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="garments",
    )

    name = models.CharField(
        max_length=150
    )

    image = models.ImageField(
        upload_to=garment_image_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "jpg",
                    "jpeg",
                    "png",
                    "webp",
                ]
            )
        ],
    )

    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_OTHER,
    )

    color = models.CharField(
        max_length=100,
        blank=True,
    )

    secondary_colors = models.JSONField(
        default=list,
        blank=True,
    )

    material = models.CharField(
        max_length=100,
        blank=True,
    )

    pattern = models.CharField(
        max_length=100,
        blank=True,
    )

    formality = models.CharField(
        max_length=30,
        choices=FORMALITY_CHOICES,
        default=FORMALITY_CASUAL,
    )

    season = models.CharField(
        max_length=100,
        blank=True,
    )

    weather_suitability = models.JSONField(
        default=list,
        blank=True,
    )

    description = models.TextField(
        blank=True,
    )

    ai_confidence = models.FloatField(
        null=True,
        blank=True,
    )

    ai_analyzed = models.BooleanField(
        default=False,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_AVAILABLE,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "status"]
            ),
            models.Index(
                fields=["user", "category"]
            ),
        ]

    def __str__(self):
        return self.name


class GarmentAnalysis(models.Model):
    garment = models.OneToOneField(
        Garment,
        on_delete=models.CASCADE,
        related_name="analysis",
    )

    raw_response = models.JSONField(
        default=dict,
        blank=True,
    )

    model_name = models.CharField(
        max_length=100,
        blank=True,
    )

    analyzed_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"AI analysis - {self.garment.name}"