
import time
from datetime import timedelta

import requests

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .models import WeatherForecast


FRESH_FORECAST_CACHE_SECONDS = 60 * 60
STALE_FORECAST_CACHE_SECONDS = 60 * 60 * 24
MAX_RETRIES = 3
RETRY_DELAYS = (2, 4, 8)


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
    city = city.strip()

    if not city:
        raise ValueError("City is required.")

    city_key = city.lower()
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
            "Weather geocoding service is temporarily "
            "rate-limited. Please try again shortly.",
            response=response,
        )

    response.raise_for_status()

    data = response.json()
    results = data.get("results") or []

    if not results:
        raise ValueError(f"Could not find the city: {city}")

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


def _forecast_cache_keys(params):
    latitude = round(float(params["latitude"]), 3)
    longitude = round(float(params["longitude"]), 3)

    base_key = (
        f"open_meteo_forecast:"
        f"{latitude}:{longitude}:"
        f"{params.get('timezone', 'auto')}"
    )

    return (
        f"{base_key}:fresh",
        f"{base_key}:stale",
    )


def _request_forecast(params):
    fresh_key, stale_key = _forecast_cache_keys(params)

    cached_data = cache.get(fresh_key)

    if cached_data is not None:
        return cached_data

    stale_data = cache.get(stale_key)

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                settings.WEATHER_API_URL,
                params=params,
                timeout=15,
            )

            if response.status_code == 429:
                if attempt == MAX_RETRIES - 1:
                    break

                retry_after = response.headers.get("Retry-After")

                try:
                    delay = int(retry_after)
                    delay = max(1, min(delay, 10))
                except (TypeError, ValueError):
                    delay = RETRY_DELAYS[attempt]

                time.sleep(delay)
                continue

            if response.status_code >= 500:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAYS[attempt])
                    continue

                response.raise_for_status()

            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict) or not data.get("daily"):
                raise ValueError(
                    "Weather API returned invalid forecast data."
                )

            cache.set(
                fresh_key,
                data,
                timeout=FRESH_FORECAST_CACHE_SECONDS,
            )

            cache.set(
                stale_key,
                data,
                timeout=STALE_FORECAST_CACHE_SECONDS,
            )

            return data

        except requests.RequestException:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAYS[attempt])
                continue

            break

    # Use the last successful response only as a fallback.
    # The caller still verifies that all requested dates exist.
    if stale_data is not None:
        return stale_data

    raise requests.HTTPError(
        "Weather service is temporarily unavailable or "
        "rate-limited. Please try again in a few minutes."
    )


def _get_user_forecasts(
    user,
    start_date,
    end_date,
    latitude,
    longitude,
):
    forecasts = list(
        WeatherForecast.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=end_date,
        ).order_by("date")
    )

    expected_count = (end_date - start_date).days + 1

    if len(forecasts) != expected_count:
        return None

    expected_dates = {
        start_date + timedelta(days=offset)
        for offset in range(expected_count)
    }

    actual_dates = {forecast.date for forecast in forecasts}

    if actual_dates != expected_dates:
        return None

    tolerance = 0.01

    for forecast in forecasts:
        if (
            abs(forecast.latitude - latitude) > tolerance
            or abs(forecast.longitude - longitude) > tolerance
        ):
            return None

    return forecasts


def _get_shared_forecasts(
    start_date,
    end_date,
    latitude,
    longitude,
):
    tolerance = 0.01

    forecasts = list(
        WeatherForecast.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
            latitude__gte=latitude - tolerance,
            latitude__lte=latitude + tolerance,
            longitude__gte=longitude - tolerance,
            longitude__lte=longitude + tolerance,
        ).order_by("date", "id")
    )

    if not forecasts:
        return None

    expected_count = (end_date - start_date).days + 1

    expected_dates = {
        start_date + timedelta(days=offset)
        for offset in range(expected_count)
    }

    grouped = {}

    for forecast in forecasts:
        grouped.setdefault(forecast.user_id, []).append(forecast)

    for user_forecasts in grouped.values():
        if len(user_forecasts) != expected_count:
            continue

        dates = {forecast.date for forecast in user_forecasts}

        if dates == expected_dates:
            return user_forecasts

    return None


def _copy_forecasts_for_user(
    source_forecasts,
    user,
    start_date,
    end_date,
):
    with transaction.atomic():
        WeatherForecast.objects.filter(
            user=user,
            date__gte=start_date,
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


def fetch_week_weather(
    user,
    city,
    start_date=None,
    end_date=None,
):
    if not city or not city.strip():
        raise ValueError("City is required for weather forecast.")

    today = timezone.localdate()

    if start_date is None:
        start_date = today

    if end_date is None:
        end_date = start_date + timedelta(days=6)

    if start_date > end_date:
        raise ValueError("Invalid weather date range.")

    if start_date < today:
        raise ValueError("Weather forecast cannot start in the past.")

    days_needed = (end_date - today).days + 1

    if days_needed > 16:
        raise ValueError(
            "Weather forecast is not available that far in advance."
        )

    latitude, longitude = get_city_coordinates(city)

    user_forecasts = _get_user_forecasts(
        user=user,
        start_date=start_date,
        end_date=end_date,
        latitude=latitude,
        longitude=longitude,
    )

    if user_forecasts is not None:
        return user_forecasts

    shared_forecasts = _get_shared_forecasts(
        start_date=start_date,
        end_date=end_date,
        latitude=latitude,
        longitude=longitude,
    )

    if shared_forecasts is not None:
        return _copy_forecasts_for_user(
            source_forecasts=shared_forecasts,
            user=user,
            start_date=start_date,
            end_date=end_date,
        )

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_probability_max",
            "rain_sum",
            "wind_speed_10m_max",
        ]),
        "timezone": "auto",
        # Request the full supported horizon so the same cached
        # response can serve both current-week and next-week plans.
        "forecast_days": 16,
    }

    data = _request_forecast(params)
    daily = data.get("daily") or {}

    dates = daily.get("time") or []

    if not dates:
        raise ValueError("Weather API returned no forecast data.")

    required_fields = [
        "weather_code",
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_probability_max",
        "rain_sum",
        "wind_speed_10m_max",
    ]

    for field in required_fields:
        if not isinstance(daily.get(field), list):
            raise ValueError(
                f"Weather API returned incomplete data: {field}."
            )

    forecasts_data = []

    for index, date_string in enumerate(dates):
        if not (str(start_date) <= date_string <= str(end_date)):
            continue

        try:
            weather_code = int(daily["weather_code"][index])
            temperature_min = float(
                daily["temperature_2m_min"][index]
            )
            temperature_max = float(
                daily["temperature_2m_max"][index]
            )

            precipitation_value = (
                daily["precipitation_probability_max"][index]
            )
            rain_value = daily["rain_sum"][index]
            wind_value = daily["wind_speed_10m_max"][index]

            precipitation_probability = int(
                precipitation_value or 0
            )
            rain_sum = float(rain_value or 0)
            wind_speed = float(wind_value or 0)

        except (IndexError, TypeError, ValueError) as exc:
            raise ValueError(
                "Weather API returned incomplete data "
                "for the selected dates."
            ) from exc

        forecasts_data.append({
            "date": date_string,
            "latitude": latitude,
            "longitude": longitude,
            "temperature_min": temperature_min,
            "temperature_max": temperature_max,
            "precipitation_probability": precipitation_probability,
            "rain": rain_sum > 0,
            "wind_speed": wind_speed,
            "weather_code": weather_code,
            "raw_data": {
                "description": weather_description(weather_code),
            },
        })

    expected_count = (end_date - start_date).days + 1

    if len(forecasts_data) != expected_count:
        raise ValueError(
            "Weather forecast is not available for every "
            "selected date yet. Please try again later."
        )

    with transaction.atomic():
        WeatherForecast.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=end_date,
        ).delete()

        forecasts = []

        for forecast_data in forecasts_data:
            forecast = WeatherForecast.objects.create(
                user=user,
                **forecast_data,
            )
            forecasts.append(forecast)

    return forecasts
