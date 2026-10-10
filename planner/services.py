
import json
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from openai import OpenAI

from wardrobe.models import Garment
from weather.services import fetch_week_weather

from .models import Outfit, OutfitItem, WeeklyPlan


def build_garment_context(garments):
    result = []

    for garment in garments:
        result.append(
            {
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
            }
        )

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
    week_end = week_start + timedelta(days=6)

    if week_start <= today <= week_end:
        start_date = today
    else:
        start_date = week_start

    return start_date, week_end


def parse_ai_response(text):
    text = text.strip()

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
            raise ValueError(
                "The AI returned invalid JSON."
            ) from exc

    if not isinstance(data, dict):
        raise ValueError("The AI response must be a JSON object.")

    outfits = data.get("outfits")

    if not isinstance(outfits, list):
        raise ValueError("The AI response has no valid outfits list.")

    return outfits


def generate_outfits(weekly_plan):
    user = weekly_plan.user

    delete_expired_outfits(user)

    garments = list(
        Garment.objects.filter(
            user=user,
            status=Garment.STATUS_AVAILABLE,
            ai_analyzed=True,
        )
    )

    if not garments:
        raise ValueError(
            "You need at least one analyzed and available garment."
        )

    start_date, end_date = get_plan_date_range(weekly_plan)

    forecasts = fetch_week_weather(
        user=user,
        city=weekly_plan.city,
        start_date=start_date,
        end_date=end_date,
    )

    if not forecasts:
        raise ValueError(
            "No weather forecasts are available for these dates."
        )

    forecasts = sorted(forecasts, key=lambda forecast: forecast.date)

    expected_dates = {
        start_date + timedelta(days=offset)
        for offset in range((end_date - start_date).days + 1)
    }

    forecast_dates = {forecast.date for forecast in forecasts}

    if forecast_dates != expected_dates:
        raise ValueError(
            "Weather data is incomplete for the selected dates. "
            "Please try again later."
        )

    garment_context = build_garment_context(garments)

    weather_context = [
        {
            "date": str(forecast.date),
            "temperature_min": forecast.temperature_min,
            "temperature_max": forecast.temperature_max,
            "rain": forecast.rain,
            "precipitation_probability": (
                forecast.precipitation_probability
            ),
            "wind_speed": forecast.wind_speed,
            "description": forecast.raw_data.get("description", ""),
        }
        for forecast in forecasts
    ]

    prompt = f"""
Create exactly one practical outfit for each date in the weather data.

City: {weekly_plan.city}
User notes: {weekly_plan.notes or "None"}

Available garments (use only these IDs):
{json.dumps(garment_context, ensure_ascii=False)}

Weather by date:
{json.dumps(weather_context, ensure_ascii=False)}

Rules:
- Return one outfit for every supplied date, with the exact date.
- Use only garment IDs listed above.
- Use each garment ID at most once in an outfit.
- Consider weather, temperature, rain, wind, season, formality and style.
- Do not invent garments or IDs.
- Dresses do not require a separate bottom.
- Choose only garments that work together.
- Keep titles and explanations short.
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

    if set(prepared_outfits) != {
        str(date) for date in expected_dates
    }:
        raise ValueError(
            "The AI did not produce a complete, valid outfit "
            "for every forecast date. Please try generating again."
        )

    with transaction.atomic():
        weekly_plan.outfits.all().delete()

        for outfit_date in sorted(prepared_outfits):
            prepared = prepared_outfits[outfit_date]
            item = prepared["data"]
            forecast = prepared["forecast"]

            outfit = Outfit.objects.create(
                weekly_plan=weekly_plan,
                date=forecast.date,
                title=str(item.get("title") or "AI Outfit")[:200],
                explanation=str(item.get("explanation") or ""),
                temperature_min=forecast.temperature_min,
                temperature_max=forecast.temperature_max,
                weather_summary=forecast.raw_data.get(
                    "description",
                    "",
                ),
            )

            for order, (garment, role) in enumerate(
                prepared["items"]
            ):
                OutfitItem.objects.create(
                    outfit=outfit,
                    garment=garment,
                    role=role,
                    order=order,
                )

        weekly_plan.status = WeeklyPlan.STATUS_GENERATED
        weekly_plan.save(
            update_fields=["status", "updated_at"]
        )

    return weekly_plan
