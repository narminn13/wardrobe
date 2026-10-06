import requests
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import WeatherForecast


def weather_description(code):
    mapping = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        80: "Rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        95: "Thunderstorm",
        96: "Thunderstorm with hail",
        99: "Thunderstorm with heavy hail",
    }

    return mapping.get(code, "Unknown")


def get_city_coordinates(city):
    response = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={
            "name": city,
            "count": 1,
            "language": "en",
            "format": "json",
        },
        timeout=15,
    )

    response.raise_for_status()

    data = response.json()
    results = data.get("results", [])

    if not results:
        raise ValueError(
            f"Could not find the city: {city}"
        )

    result = results[0]

    return (
        float(result["latitude"]),
        float(result["longitude"]),
    )


def fetch_week_weather(user, city):
    if not city:
        raise ValueError(
            "City is required for weather forecast."
        )

    latitude, longitude = get_city_coordinates(city)

    today = timezone.localdate()

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join(
            [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
                "rain_sum",
                "wind_speed_10m_max",
            ]
        ),
        "timezone": "auto",
        "forecast_days": 7,
    }

    response = requests.get(
        settings.WEATHER_API_URL,
        params=params,
        timeout=15,
    )

    response.raise_for_status()

    data = response.json()
    daily = data.get("daily", {})

    dates = daily.get("time", [])

    if not dates:
        raise ValueError(
            "Weather API returned no forecast data."
        )

    WeatherForecast.objects.filter(
        user=user,
        date__gte=today,
        date__lte=today + timedelta(days=6),
    ).delete()

    forecasts = []

    for index, date_string in enumerate(dates):
        weather_code = int(
            daily["weather_code"][index]
        )

        rain_sum = float(
            daily["rain_sum"][index] or 0
        )

        precipitation_probability = int(
            daily[
                "precipitation_probability_max"
            ][index] or 0
        )

        forecast = WeatherForecast.objects.create(
            user=user,
            date=date_string,
            latitude=latitude,
            longitude=longitude,
            temperature_min=float(
                daily[
                    "temperature_2m_min"
                ][index]
            ),
            temperature_max=float(
                daily[
                    "temperature_2m_max"
                ][index]
            ),
            precipitation_probability=(
                precipitation_probability
            ),
            rain=rain_sum > 0,
            wind_speed=float(
                daily[
                    "wind_speed_10m_max"
                ][index] or 0
            ),
            weather_code=weather_code,
            raw_data={
                "description": weather_description(
                    weather_code
                )
            },
        )

        forecasts.append(forecast)

    return forecasts