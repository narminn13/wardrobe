import time
from datetime import timedelta

import requests

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
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
    city_key = city.strip().lower()

    cache_key = f"weather_coordinates:{city_key}"

    cached_coordinates = cache.get(cache_key)

    if cached_coordinates is not None:
        return cached_coordinates

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

    if response.status_code == 429:
        raise requests.HTTPError(
            "Weather geocoding service is temporarily rate-limited.",
            response=response,
        )

    response.raise_for_status()

    data = response.json()

    results = data.get("results", [])

    if not results:
        raise ValueError(
            f"Could not find the city: {city}"
        )

    result = results[0]

    coordinates = (
        float(result["latitude"]),
        float(result["longitude"]),
    )

    cache.set(
        cache_key,
        coordinates,
        timeout=60 * 60 * 24 * 30,
    )

    return coordinates


def _get_user_forecasts(
    user,
    today,
    latitude,
    longitude,
):
    end_date = today + timedelta(days=6)

    forecasts = list(
        WeatherForecast.objects.filter(
            user=user,
            date__gte=today,
            date__lte=end_date,
        ).order_by("date")
    )

    if len(forecasts) != 7:
        return None

    tolerance = 0.01

    for forecast in forecasts:
        if (
            abs(forecast.latitude - latitude)
            > tolerance
            or abs(forecast.longitude - longitude)
            > tolerance
        ):
            return None

    return forecasts


def _get_shared_forecasts(
    today,
    latitude,
    longitude,
):
    end_date = today + timedelta(days=6)

    tolerance = 0.01

    forecasts = list(
        WeatherForecast.objects.filter(
            date__gte=today,
            date__lte=end_date,
            latitude__gte=latitude - tolerance,
            latitude__lte=latitude + tolerance,
            longitude__gte=longitude - tolerance,
            longitude__lte=longitude + tolerance,
        )
        .select_related("user")
        .order_by(
            "date",
            "id",
        )
    )

    if not forecasts:
        return None

    grouped = {}

    for forecast in forecasts:
        grouped.setdefault(
            forecast.user_id,
            [],
        ).append(forecast)

    for user_forecasts in grouped.values():
        if len(user_forecasts) != 7:
            continue

        dates = {
            forecast.date
            for forecast in user_forecasts
        }

        expected_dates = {
            today + timedelta(days=offset)
            for offset in range(7)
        }

        if dates == expected_dates:
            return user_forecasts

    return None


def _copy_forecasts_for_user(
    source_forecasts,
    user,
    today,
):
    end_date = today + timedelta(days=6)

    with transaction.atomic():
        WeatherForecast.objects.filter(
            user=user,
            date__gte=today,
            date__lte=end_date,
        ).delete()

        forecasts = []

        for source in source_forecasts:
            forecast = WeatherForecast.objects.create(
                user=user,
                date=source.date,
                latitude=source.latitude,
                longitude=source.longitude,
                temperature_min=source.temperature_min,
                temperature_max=source.temperature_max,
                precipitation_probability=(
                    source.precipitation_probability
                ),
                rain=source.rain,
                wind_speed=source.wind_speed,
                weather_code=source.weather_code,
                raw_data=source.raw_data,
            )

            forecasts.append(forecast)

    return forecasts


def _request_forecast(params):
    max_attempts = 3
    delays = [3, 7, 15]

    for attempt in range(max_attempts):
        response = requests.get(
            settings.WEATHER_API_URL,
            params=params,
            timeout=15,
        )

        if response.status_code == 429:
            if attempt == max_attempts - 1:
                raise requests.HTTPError(
                    "Weather service is temporarily rate-limited. "
                    "Please try again in a few minutes.",
                    response=response,
                )

            time.sleep(delays[attempt])

            continue

        response.raise_for_status()

        return response.json()

    raise ValueError(
        "Weather API request failed."
    )


def fetch_week_weather(user, city):
    if not city:
        raise ValueError(
            "City is required for weather forecast."
        )

    today = timezone.localdate()

    latitude, longitude = get_city_coordinates(city)

    user_forecasts = _get_user_forecasts(
        user=user,
        today=today,
        latitude=latitude,
        longitude=longitude,
    )

    if user_forecasts is not None:
        return user_forecasts

    shared_forecasts = _get_shared_forecasts(
        today=today,
        latitude=latitude,
        longitude=longitude,
    )

    if shared_forecasts is not None:
        return _copy_forecasts_for_user(
            source_forecasts=shared_forecasts,
            user=user,
            today=today,
        )

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

    data = _request_forecast(params)

    daily = data.get("daily", {})

    dates = daily.get("time", [])

    if not dates:
        raise ValueError(
            "Weather API returned no forecast data."
        )

    forecasts_data = []

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

        forecasts_data.append(
            {
                "date": date_string,
                "latitude": latitude,
                "longitude": longitude,
                "temperature_min": float(
                    daily[
                        "temperature_2m_min"
                    ][index]
                ),
                "temperature_max": float(
                    daily[
                        "temperature_2m_max"
                    ][index]
                ),
                "precipitation_probability": (
                    precipitation_probability
                ),
                "rain": rain_sum > 0,
                "wind_speed": float(
                    daily[
                        "wind_speed_10m_max"
                    ][index] or 0
                ),
                "weather_code": weather_code,
                "raw_data": {
                    "description": weather_description(
                        weather_code
                    )
                },
            }
        )

    WeatherForecast.objects.filter(
        user=user,
        date__gte=today,
        date__lte=today + timedelta(days=6),
    ).delete()

    forecasts = []

    for forecast_data in forecasts_data:
        forecast = WeatherForecast.objects.create(
            user=user,
            **forecast_data,
        )

        forecasts.append(forecast)

    return forecasts