import base64
import io
import json

from django.conf import settings
from PIL import Image
from openai import OpenAI

from .models import Garment, GarmentAnalysis


client = OpenAI(
    api_key=settings.OPENAI_API_KEY
)


def optimize_image(file):
    file.seek(0)

    image = Image.open(file)

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")

    image.thumbnail((1200, 1200))

    output = io.BytesIO()

    if image.mode == "RGBA":
        image.save(
            output,
            format="WEBP",
            quality=82
        )
        mime_type = "image/webp"
    else:
        image = image.convert("RGB")
        image.save(
            output,
            format="JPEG",
            quality=82,
            optimize=True
        )
        mime_type = "image/jpeg"

    encoded = base64.b64encode(
        output.getvalue()
    ).decode("utf-8")

    return f"data:{mime_type};base64,{encoded}"


def analyze_garment_image(file):
    image_data = optimize_image(file)

    prompt = """
Analyze the clothing item in the image.

Return ONLY valid JSON.
Do not use markdown.
Do not add explanations outside the JSON.

Use exactly this structure:

{
    "name": "",
    "category": "",
    "color": "",
    "secondary_colors": [],
    "material": "",
    "pattern": "",
    "formality": "",
    "season": "",
    "weather_suitability": [],
    "description": "",
    "confidence": 0.0
}

Allowed category values:
top, bottom, dress, outerwear, shoes, accessory, other

Allowed formality values:
casual, smart_casual, formal, sport, other

For weather_suitability use values such as:
hot, warm, mild, cool, cold, rainy, windy, snowy

For confidence use a number between 0 and 1.

Be conservative.
If something cannot be determined confidently,
use "other" or an empty value.
"""

    try:
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt
                        },
                        {
                            "type": "input_image",
                            "image_url": image_data,
                            "detail": "auto"
                        }
                    ]
                }
            ],
            max_output_tokens=1000
        )
    except Exception as exc:
        raise RuntimeError(
            f"OpenAI API error: {exc}"
        ) from exc

    text = response.output_text.strip()

    if not text:
        raise ValueError(
            "OpenAI returned an empty response."
        )

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1:
            raise ValueError(
                f"AI returned invalid JSON: {text}"
            )

        try:
            data = json.loads(
                text[start:end + 1]
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"AI returned invalid JSON: {text}"
            ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            "AI response is not a JSON object."
        )

    return data


def save_garment_analysis(garment, data):
    valid_categories = {
        value
        for value, _ in garment.CATEGORY_CHOICES
    }

    valid_formality = {
        value
        for value, _ in garment.FORMALITY_CHOICES
    }

    category = data.get(
        "category",
        "other"
    )

    if category not in valid_categories:
        category = "other"

    formality = data.get(
        "formality",
        "other"
    )

    if formality not in valid_formality:
        formality = "other"

    garment.name = (
        data.get("name")
        or garment.name
        or "Unnamed garment"
    )[:150]

    garment.category = category

    garment.color = str(
        data.get("color", "")
    )[:100]

    secondary_colors = data.get(
        "secondary_colors",
        []
    )

    if not isinstance(
        secondary_colors,
        list
    ):
        secondary_colors = []

    garment.secondary_colors = (
        secondary_colors
    )

    garment.material = str(
        data.get("material", "")
    )[:100]

    garment.pattern = str(
        data.get("pattern", "")
    )[:100]

    garment.formality = formality

    garment.season = str(
        data.get("season", "")
    )[:100]

    weather_suitability = data.get(
        "weather_suitability",
        []
    )

    if not isinstance(
        weather_suitability,
        list
    ):
        weather_suitability = []

    garment.weather_suitability = (
        weather_suitability
    )

    garment.description = str(
        data.get("description", "")
    )

    try:
        confidence = float(
            data.get("confidence", 0)
        )

        confidence = max(
            0.0,
            min(1.0, confidence)
        )

        garment.ai_confidence = confidence

    except (TypeError, ValueError):
        garment.ai_confidence = None

    garment.ai_analyzed = True

    garment.save()

    GarmentAnalysis.objects.update_or_create(
        garment=garment,
        defaults={
            "raw_response": data,
            "model_name": settings.OPENAI_MODEL
        }
    )