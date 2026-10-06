from django.db import models


class WeatherForecast(models.Model):
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="weather_forecasts",
    )

    date = models.DateField()

    latitude = models.FloatField()

    longitude = models.FloatField()

    temperature_min = models.FloatField()

    temperature_max = models.FloatField()

    precipitation_probability = models.IntegerField(
        default=0
    )

    rain = models.BooleanField(
        default=False
    )

    wind_speed = models.FloatField(
        default=0
    )

    weather_code = models.IntegerField(
        default=0
    )

    raw_data = models.JSONField(
        default=dict,
        blank=True,
    )

    fetched_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["date"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "date",
                ],
                name="unique_user_weather_date",
            )
        ]

    def __str__(self):
        return f"{self.user.email} - {self.date}"