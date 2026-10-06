from django.conf import settings
from django.db import models


class WeeklyPlan(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_GENERATED = "generated"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_GENERATED, "Generated"),
        (STATUS_FAILED, "Failed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weekly_plans",
    )

    week_start = models.DateField()

    city = models.CharField(
        max_length=100
    )

    preferred_formality = models.CharField(
        max_length=30,
        default="casual"
    )

    notes = models.TextField(
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-week_start"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "week_start",
                ],
                name="unique_user_week",
            )
        ]

    def __str__(self):
        return f"{self.user.email} - {self.week_start}"


class Outfit(models.Model):
    weekly_plan = models.ForeignKey(
        WeeklyPlan,
        on_delete=models.CASCADE,
        related_name="outfits",
    )

    date = models.DateField()

    title = models.CharField(
        max_length=200
    )

    explanation = models.TextField(
        blank=True
    )

    temperature_min = models.FloatField(
        null=True,
        blank=True
    )

    temperature_max = models.FloatField(
        null=True,
        blank=True
    )

    weather_summary = models.CharField(
        max_length=200,
        blank=True
    )

    generated_by_ai = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["date"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "weekly_plan",
                    "date",
                ],
                name="unique_plan_outfit_date",
            )
        ]

    def __str__(self):
        return f"{self.date} - {self.title}"


class OutfitItem(models.Model):
    outfit = models.ForeignKey(
        Outfit,
        on_delete=models.CASCADE,
        related_name="items",
    )

    garment = models.ForeignKey(
        "wardrobe.Garment",
        on_delete=models.PROTECT,
        related_name="outfit_items",
    )

    role = models.CharField(
        max_length=50,
        default="item"
    )

    order = models.PositiveIntegerField(
        default=0
    )

    class Meta:
        ordering = ["order"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "outfit",
                    "garment",
                ],
                name="unique_outfit_garment",
            )
        ]

    def __str__(self):
        return f"{self.outfit} - {self.garment.name}"