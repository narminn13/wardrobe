import json

from django.conf import settings
from django.db import transaction
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
                "formality": garment.formality,
                "season": garment.season,
                "weather_suitability": garment.weather_suitability,
                "description": garment.description,
            }
        )

    return result


def generate_outfits(weekly_plan):
    user = weekly_plan.user

    forecasts = fetch_week_weather(
        user,
        weekly_plan.city,
    )

    garments = list(
        Garment.objects.filter(
            user=user,
            status=Garment.STATUS_AVAILABLE,
            ai_analyzed=True,
        )
    )

    if not garments:
        raise ValueError(
            "You need at least one analyzed garment."
        )

    if not forecasts:
        raise ValueError(
            "Weather forecast could not be loaded."
        )

    garment_context = build_garment_context(garments)

    weather_context = []

    for forecast in forecasts:
        weather_context.append(
            {
                "date": str(forecast.date),
                "temperature_min": forecast.temperature_min,
                "temperature_max": forecast.temperature_max,
                "rain": forecast.rain,
                "precipitation_probability": (
                    forecast.precipitation_probability
                ),
                "wind_speed": forecast.wind_speed,
                "description": forecast.raw_data.get(
                    "description",
                    "",
                ),
            }
        )

    prompt = f"""
You are an AI personal wardrobe planner.

Create outfits for every forecast day.

User city:
{weekly_plan.city}

Preferred formality:
{weekly_plan.preferred_formality}

User notes:
{weekly_plan.notes}

Available garments:
{json.dumps(garment_context)}

Weather:
{json.dumps(weather_context)}

Rules:

1. Only use garment IDs from the available garments.
2. Do not use unavailable garments.
3. Consider temperature.
4. Consider rain.
5. Consider wind.
6. Consider formality.
7. Avoid unreasonable combinations.
8. Try to vary outfits across the week.
9. If a dress is selected, do not require a bottom.
10. Shoes can be included when available.
11. Every day must have an outfit.
12. Do not invent garment IDs.

Return ONLY valid JSON in this format:

{{
    "outfits": [
        {{
            "date": "YYYY-MM-DD",
            "title": "string",
            "explanation": "string",
            "garment_ids": [1, 2, 3],
            "roles": {{
                "1": "top",
                "2": "bottom",
                "3": "shoes"
            }}
        }}
    ]
}}
"""

    client = OpenAI(
        api_key=settings.OPENAI_API_KEY
    )

    response = client.responses.create(
        model=settings.OPENAI_MODEL,
        input=prompt,
        max_output_tokens=3000,
    )

    text = response.output_text.strip()

    if not text:
        raise ValueError(
            "AI returned an empty response."
        )

    try:
        data = json.loads(text)

    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1:
            raise ValueError(
                "AI returned invalid outfit data."
            )

        try:
            data = json.loads(
                text[start:end + 1]
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"AI returned invalid outfit data: {text}"
            ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            "AI returned invalid outfit data."
        )

    outfits_data = data.get("outfits", [])

    if not isinstance(outfits_data, list):
        raise ValueError(
            "AI returned invalid outfits structure."
        )

    garment_map = {
        garment.id: garment
        for garment in garments
    }

    with transaction.atomic():
        weekly_plan.outfits.all().delete()

        created_count = 0

        for item in outfits_data:
            if not isinstance(item, dict):
                continue

            outfit_date = item.get("date")

            forecast = next(
                (
                    forecast
                    for forecast in forecasts
                    if str(forecast.date) == str(outfit_date)
                ),
                None,
            )

            if forecast is None:
                continue

            outfit = Outfit.objects.create(
                weekly_plan=weekly_plan,
                date=forecast.date,
                title=str(
                    item.get(
                        "title",
                        "AI Outfit",
                    )
                )[:200],
                explanation=str(
                    item.get(
                        "explanation",
                        "",
                    )
                ),
                temperature_min=forecast.temperature_min,
                temperature_max=forecast.temperature_max,
                weather_summary=forecast.raw_data.get(
                    "description",
                    "",
                ),
            )

            garment_ids = item.get(
                "garment_ids",
                [],
            )

            roles = item.get(
                "roles",
                {},
            )

            if not isinstance(garment_ids, list):
                garment_ids = []

            if not isinstance(roles, dict):
                roles = {}

            for order, garment_id in enumerate(
                garment_ids
            ):
                try:
                    garment_id = int(garment_id)
                except (TypeError, ValueError):
                    continue

                garment = garment_map.get(garment_id)

                if garment is None:
                    continue

                OutfitItem.objects.create(
                    outfit=outfit,
                    garment=garment,
                    role=str(
                        roles.get(
                            str(garment_id),
                            "item",
                        )
                    ),
                    order=order,
                )

            created_count += 1

        if created_count == 0:
            raise ValueError(
                "AI did not generate any valid outfits."
            )

        weekly_plan.status = WeeklyPlan.STATUS_GENERATED

        weekly_plan.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

    return weekly_plan