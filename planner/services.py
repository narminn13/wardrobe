
import json
from datetime import date, timedelta
from types import SimpleNamespace

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from openai import OpenAI

from wardrobe.models import Garment
from weather.services import fetch_week_weather

from .models import Outfit, OutfitItem, WeeklyPlan


class WeatherUnavailableError(Exception):
    """Raised when reliable weather data cannot be obtained."""


def build_garment_context(garments):
    result = []

    for garment in garments:
        result.append({
            "id": garment.id,
            "name": garment.name,
            "category": garment.category,
            "color": garment.color,
            "secondary_colors": garment.secondary_colors,
            "material": garment.material,
            "pattern": garment.pattern,
            "fit": getattr(garment, "fit", ""),
            "style": getattr(garment, "style", ""),
            "formality": garment.formality,
            "season": garment.season,
            "warmth": getattr(garment, "warmth", ""),
            "weather_suitability": garment.weather_suitability,
            "description": garment.description,
        })

    return result


def delete_expired_outfits(user):
    today = timezone.localdate()

    Outfit.objects.filter(
        weekly_plan__user=user,
        date__lt=today,
    ).delete()


def get_plan_date_range(weekly_plan):
    today = timezone.localdate()
    week_start = weekly_plan.week_start

    # DateField normally returns a date, but tests or manually
    # constructed objects may supply an ISO-formatted string.
    if isinstance(week_start, str):
        try:
            week_start = date.fromisoformat(week_start)
        except ValueError as exc:
            raise ValueError(
                "The weekly plan has an invalid start date."
            ) from exc

    if not isinstance(week_start, date):
        raise ValueError(
            "The weekly plan has an invalid start date."
        )

    week_end = week_start + timedelta(days=6)

    if week_start <= today <= week_end:
        start_date = today
    else:
        start_date = week_start

    return start_date, week_end


def parse_json_object(text):
    text = (text or "").strip()

    if not text:
        raise ValueError("The AI returned an empty response.")

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end <= start:
            raise ValueError("The AI returned invalid JSON.")

        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("The AI returned invalid JSON.") from exc

    if not isinstance(data, dict):
        raise ValueError("The AI response must be a JSON object.")

    return data


def parse_ai_response(text):
    data = parse_json_object(text)
    outfits = data.get("outfits")

    if not isinstance(outfits, list):
        raise ValueError("The AI response has no valid outfits list.")

    return outfits


def estimate_weather(city, start_date, end_date):
    """
    Generate approximate seasonal estimates.
    These are not live observations or an official forecast.
    """
    dates = [
        start_date + timedelta(days=offset)
        for offset in range((end_date - start_date).days + 1)
    ]
    date_list = [str(day) for day in dates]

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    prompt = f"""
Create rough seasonal weather estimates for clothing recommendations.

City: {city}
Dates: {json.dumps(date_list)}

Important:
- You do not have access to live weather data.
- Do not claim these values are an actual forecast.
- Use general geographic and seasonal knowledge for this city.
- If uncertain, use conservative estimates and describe uncertainty.
- Return exactly one entry for every supplied date.
- Temperatures must be in Celsius.
- Rain probability must be an integer from 0 to 100.
- Wind speed must be in kilometres per hour.
- Minimum temperature must not exceed maximum temperature.
- Keep descriptions short.
- Return only valid JSON, without Markdown.

Required format:
{{
  "weather": [
    {{
      "date": "YYYY-MM-DD",
      "temperature_min": 12,
      "temperature_max": 18,
      "rain_probability": 30,
      "wind_speed": 12,
      "description": "Partly cloudy; approximate seasonal conditions"
    }}
  ]
}}
"""

    response = client.responses.create(
        model=settings.OPENAI_MODEL,
        input=prompt,
        max_output_tokens=3000,
    )

    data = parse_json_object(response.output_text)
    weather_items = data.get("weather")

    if not isinstance(weather_items, list):
        raise ValueError("Estimated weather data is invalid.")

    expected_dates = set(date_list)
    weather_by_date = {}

    for item in weather_items:
        if not isinstance(item, dict):
            continue

        date_string = str(item.get("date", ""))

        if date_string not in expected_dates:
            continue

        try:
            temperature_min = float(item["temperature_min"])
            temperature_max = float(item["temperature_max"])
            rain_probability = int(item["rain_probability"])
            wind_speed = float(item["wind_speed"])
        except (KeyError, TypeError, ValueError):
            continue

        if temperature_min > temperature_max:
            continue

        if not -80 <= temperature_min <= 65:
            continue

        if not -80 <= temperature_max <= 65:
            continue

        if not 0 <= rain_probability <= 100:
            continue

        if not 0 <= wind_speed <= 250:
            continue

        description = str(
            item.get("description")
            or "Approximate seasonal conditions"
        )[:150]

        forecast_date = dates[date_list.index(date_string)]

        weather_by_date[date_string] = SimpleNamespace(
            date=forecast_date,
            temperature_min=temperature_min,
            temperature_max=temperature_max,
            precipitation_probability=rain_probability,
            rain=rain_probability >= 40,
            wind_speed=wind_speed,
            raw_data={
                "description": description,
                "estimated": True,
            },
        )

    if set(weather_by_date) != expected_dates:
        raise ValueError(
            "Estimated weather could not be prepared for every date. "
            "Please try again later."
        )

    return [
        weather_by_date[date_string]
        for date_string in date_list
    ]


def get_weather_for_plan(
    weekly_plan,
    start_date,
    end_date,
    use_estimated_weather,
):
    if use_estimated_weather:
        return estimate_weather(
            city=weekly_plan.city,
            start_date=start_date,
            end_date=end_date,
        )

    try:
        forecasts = fetch_week_weather(
            user=weekly_plan.user,
            city=weekly_plan.city,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:
        raise WeatherUnavailableError(
            "Reliable weather data is currently unavailable."
        ) from exc

    if not forecasts:
        raise WeatherUnavailableError(
            "No weather forecasts are available for these dates."
        )

    forecasts = sorted(forecasts, key=lambda forecast: forecast.date)

    expected_dates = {
        start_date + timedelta(days=offset)
        for offset in range((end_date - start_date).days + 1)
    }
    actual_dates = {forecast.date for forecast in forecasts}

    if actual_dates != expected_dates:
        raise WeatherUnavailableError(
            "Weather data is incomplete for the selected dates."
        )

    return forecasts


def generate_outfits(weekly_plan, use_estimated_weather=False):
    user = weekly_plan.user

    garments = list(
        Garment.objects.filter(
            user=user,
            status=Garment.STATUS_AVAILABLE,
            ai_analyzed=True,
        )
    )

    if not garments:
        raise ValueError(
            "You need at least one analyzed garment that is available."
        )

    start_date, end_date = get_plan_date_range(weekly_plan)

    forecasts = get_weather_for_plan(
        weekly_plan=weekly_plan,
        start_date=start_date,
        end_date=end_date,
        use_estimated_weather=use_estimated_weather,
    )
    forecasts = sorted(forecasts, key=lambda forecast: forecast.date)

    garment_context = build_garment_context(garments)
    weather_context = []

    for forecast in forecasts:
        raw_data = forecast.raw_data or {}
        description = raw_data.get("description", "")

        weather_context.append({
            "date": str(forecast.date),
            "temperature_min": forecast.temperature_min,
            "temperature_max": forecast.temperature_max,
            "rain": forecast.rain,
            "precipitation_probability": (
                forecast.precipitation_probability
            ),
            "wind_speed": forecast.wind_speed,
            "description": description,
            "estimated": bool(raw_data.get("estimated", False)),
        })

    if use_estimated_weather:
        weather_notice = (
            "Weather values are approximate seasonal estimates, not an "
            "official forecast. Do not describe them as confirmed facts."
        )
    else:
        weather_notice = (
            "Use the supplied weather-service data when recommending outfits."
        )

    prompt = f"""
Create exactly one practical outfit for each date in the weather data.

City: {weekly_plan.city}
User notes: {weekly_plan.notes or "None"}

Weather status:
{weather_notice}

Available garments (use only these IDs):
{json.dumps(garment_context, ensure_ascii=False)}

Weather by date:
{json.dumps(weather_context, ensure_ascii=False)}

Rules:
- Return one outfit for every supplied date, with the exact date.
- Use only garment IDs listed above.
- Use each garment ID at most once in an outfit.
- Consider temperature, rain, wind, season, formality and style.
- Do not invent garments or IDs.
- Dresses do not require a separate bottom.
- Choose only garments that work together.
- Keep titles and explanations short.
- Do not claim estimated weather is confirmed.
- Return only valid JSON, without Markdown or extra text.

Required format:
{{
  "outfits": [
    {{
      "date": "YYYY-MM-DD",
      "title": "Short outfit title",
      "explanation": "Short explanation",
      "garment_ids": [1, 2],
      "roles": {{
        "1": "top",
        "2": "bottom"
      }}
    }}
  ]
}}
"""

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    response = client.responses.create(
        model=settings.OPENAI_MODEL,
        input=prompt,
        max_output_tokens=5000,
    )

    outfits_data = parse_ai_response(response.output_text)

    garment_map = {
        garment.id: garment
        for garment in garments
    }
    forecast_map = {
        str(forecast.date): forecast
        for forecast in forecasts
    }
    prepared_outfits = {}

    for item in outfits_data:
        if not isinstance(item, dict):
            continue

        outfit_date = str(item.get("date", ""))

        if outfit_date not in forecast_map:
            continue

        if outfit_date in prepared_outfits:
            continue

        garment_ids = item.get("garment_ids", [])
        roles = item.get("roles", {})

        if not isinstance(garment_ids, list):
            garment_ids = []

        if not isinstance(roles, dict):
            roles = {}

        valid_items = []
        used_ids = set()

        for garment_id in garment_ids:
            try:
                garment_id = int(garment_id)
            except (TypeError, ValueError):
                continue

            garment = garment_map.get(garment_id)

            if garment is None or garment_id in used_ids:
                continue

            used_ids.add(garment_id)
            role = str(roles.get(str(garment_id), "item"))[:50]
            valid_items.append((garment, role))

        if not valid_items:
            continue

        prepared_outfits[outfit_date] = {
            "data": item,
            "forecast": forecast_map[outfit_date],
            "items": valid_items,
        }

    expected_outfit_dates = set(forecast_map)

    if set(prepared_outfits) != expected_outfit_dates:
        raise ValueError(
            "The AI did not produce a complete, valid outfit for every "
            "date. Please try generating again."
        )

    # Replace existing outfits only after all new outfits are validated.
    with transaction.atomic():
        weekly_plan.outfits.all().delete()

        for outfit_date in sorted(prepared_outfits):
            prepared = prepared_outfits[outfit_date]
            item = prepared["data"]
            forecast = prepared["forecast"]
            raw_data = forecast.raw_data or {}

            is_estimated = bool(raw_data.get("estimated", False))
            description = raw_data.get(
                "description",
                "Weather unavailable",
            )

            if is_estimated:
                weather_summary = (
                    f"Estimated* · {description} · "
                    f"Rain {forecast.precipitation_probability}%* · "
                    f"Wind {forecast.wind_speed:g} km/h*"
                )
            else:
                weather_summary = (
                    f"{description} · "
                    f"Rain {forecast.precipitation_probability}% · "
                    f"Wind {forecast.wind_speed:g} km/h"
                )

            outfit = Outfit.objects.create(
                weekly_plan=weekly_plan,
                date=forecast.date,
                title=str(item.get("title") or "AI Outfit")[:200],
                explanation=str(item.get("explanation") or ""),
                temperature_min=forecast.temperature_min,
                temperature_max=forecast.temperature_max,
                weather_summary=weather_summary,
            )

            for order, (garment, role) in enumerate(prepared["items"]):
                OutfitItem.objects.create(
                    outfit=outfit,
                    garment=garment,
                    role=role,
                    order=order,
                )

        weekly_plan.status = WeeklyPlan.STATUS_GENERATED
        weekly_plan.save(update_fields=["status", "updated_at"])

    return weekly_plan
