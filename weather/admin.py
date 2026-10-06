from django.contrib import admin

from .models import WeatherForecast


@admin.register(WeatherForecast)
class WeatherForecastAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "date",
        "temperature_min",
        "temperature_max",
        "rain",
        "wind_speed",
    ]

    list_filter = [
        "rain",
        "date",
    ]

    search_fields = [
        "user__email",
    ]