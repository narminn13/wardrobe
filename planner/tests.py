
import json
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from .models import Outfit, WeeklyPlan
from .services import WeatherUnavailableError, generate_outfits


User = get_user_model()


class WeeklyPlanTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpassword123",
        )

    def create_plan(self, week_start="2026-10-12"):
        return WeeklyPlan.objects.create(
            user=self.user,
            week_start=week_start,
            city="Baku",
            preferred_formality="casual",
            notes="Simple university outfits.",
        )

    def test_weekly_plan_can_be_created(self):
        plan = self.create_plan()

        self.assertEqual(plan.city, "Baku")
        self.assertEqual(plan.preferred_formality, "casual")
        self.assertEqual(plan.status, WeeklyPlan.STATUS_DRAFT)

    def test_same_user_cannot_create_same_week_twice(self):
        self.create_plan()

        with self.assertRaises(IntegrityError):
            self.create_plan()

    def test_different_users_can_create_same_week(self):
        second_user = User.objects.create_user(
            email="second@example.com",
            password="testpassword123",
        )

        plan1 = self.create_plan()
        plan2 = WeeklyPlan.objects.create(
            user=second_user,
            week_start="2026-10-12",
            city="Baku",
            preferred_formality="formal",
        )

        self.assertEqual(plan1.week_start, plan2.week_start)
        self.assertNotEqual(plan1.user, plan2.user)

    def test_outfit_can_be_created_for_weekly_plan(self):
        plan = self.create_plan()

        outfit = Outfit.objects.create(
            weekly_plan=plan,
            date="2026-10-12",
            title="Casual Monday",
            explanation="Comfortable outfit for university.",
            temperature_min=15,
            temperature_max=23,
            weather_summary="Partly cloudy",
        )

        self.assertEqual(outfit.weekly_plan, plan)
        self.assertEqual(outfit.title, "Casual Monday")
        self.assertEqual(outfit.temperature_max, 23)

    def test_same_plan_cannot_have_two_outfits_on_same_date(self):
        plan = self.create_plan()

        Outfit.objects.create(
            weekly_plan=plan,
            date="2026-10-12",
            title="First Outfit",
        )

        with self.assertRaises(IntegrityError):
            Outfit.objects.create(
                weekly_plan=plan,
                date="2026-10-12",
                title="Second Outfit",
            )

    def test_same_plan_can_have_outfits_on_different_dates(self):
        plan = self.create_plan()

        outfit1 = Outfit.objects.create(
            weekly_plan=plan,
            date="2026-10-12",
            title="Monday Outfit",
        )
        outfit2 = Outfit.objects.create(
            weekly_plan=plan,
            date="2026-10-13",
            title="Tuesday Outfit",
        )

        self.assertNotEqual(outfit1.date, outfit2.date)
        self.assertEqual(plan.outfits.count(), 2)

    def create_mock_forecasts(self):
        return [
            SimpleNamespace(
                date=date(2026, 10, 12) + timedelta(days=day),
                temperature_min=15,
                temperature_max=23,
                rain=False,
                precipitation_probability=10,
                wind_speed=12,
                raw_data={"description": "Partly cloudy"},
            )
            for day in range(7)
        ]

    def create_mock_garment(self):
        return SimpleNamespace(
            id=1,
            name="White Shirt",
            category="top",
            color="white",
            secondary_colors=[],
            material="cotton",
            pattern="plain",
            fit="regular",
            style="casual",
            formality="casual",
            season="all",
            warmth="light",
            weather_suitability=["mild"],
            description="White cotton shirt.",
        )

    def create_ai_response(self, forecasts, garment_ids=None):
        if garment_ids is None:
            garment_ids = [1]

        outfits = []

        for forecast in forecasts:
            outfit_date = forecast.date.isoformat()
            outfits.append(
                {
                    "date": outfit_date,
                    "title": f"Casual Outfit {outfit_date}",
                    "explanation": (
                        "A comfortable outfit for mild weather."
                    ),
                    "garment_ids": garment_ids,
                    "roles": {
                        str(garment_id): "top"
                        for garment_id in garment_ids
                    },
                }
            )

        return json.dumps({"outfits": outfits})

    def configure_openai_response(self, mock_openai, output_text):
        mock_response = Mock()
        mock_response.output_text = output_text

        mock_client = Mock()
        mock_client.responses.create.return_value = mock_response
        mock_openai.return_value = mock_client

    @patch("planner.services.fetch_week_weather")
    def test_generation_fails_when_user_has_no_garments(
        self,
        mock_weather,
    ):
        plan = self.create_plan()
        mock_weather.return_value = self.create_mock_forecasts()

        with patch(
            "planner.services.Garment.objects.filter",
            return_value=[],
        ):
            with self.assertRaises(ValueError) as context:
                generate_outfits(plan)

        self.assertIn(
            "at least one analyzed garment",
            str(context.exception),
        )

    @patch("planner.services.fetch_week_weather")
    def test_generation_fails_when_weather_is_empty(
        self,
        mock_weather,
    ):
        plan = self.create_plan()
        mock_weather.return_value = []

        with patch(
            "planner.services.Garment.objects.filter",
            return_value=[self.create_mock_garment()],
        ):
            with self.assertRaises(WeatherUnavailableError):
                generate_outfits(plan)

        plan.refresh_from_db()
        self.assertEqual(plan.status, WeeklyPlan.STATUS_DRAFT)
        self.assertEqual(plan.outfits.count(), 0)

    @patch("planner.services.fetch_week_weather")
    @patch("planner.services.Garment.objects.filter")
    @patch("planner.services.OpenAI")
    @patch("planner.services.OutfitItem.objects.create")
    def test_successful_outfit_generation(
        self,
        mock_outfit_item,
        mock_openai,
        mock_garment_filter,
        mock_weather,
    ):
        plan = self.create_plan()
        forecasts = self.create_mock_forecasts()

        mock_weather.return_value = forecasts
        mock_garment_filter.return_value = [self.create_mock_garment()]
        self.configure_openai_response(
            mock_openai,
            self.create_ai_response(forecasts),
        )

        generate_outfits(plan)

        plan.refresh_from_db()

        self.assertEqual(plan.status, WeeklyPlan.STATUS_GENERATED)
        self.assertEqual(plan.outfits.count(), 7)
        self.assertEqual(mock_outfit_item.call_count, 7)

    @patch("planner.services.fetch_week_weather")
    @patch("planner.services.Garment.objects.filter")
    @patch("planner.services.OpenAI")
    def test_generation_fails_with_invalid_ai_json(
        self,
        mock_openai,
        mock_garment_filter,
        mock_weather,
    ):
        plan = self.create_plan()
        mock_weather.return_value = self.create_mock_forecasts()
        mock_garment_filter.return_value = [self.create_mock_garment()]

        self.configure_openai_response(
            mock_openai,
            "This is not valid JSON.",
        )

        with self.assertRaises(ValueError) as context:
            generate_outfits(plan)

        self.assertIn("invalid", str(context.exception).lower())

        plan.refresh_from_db()
        self.assertEqual(plan.status, WeeklyPlan.STATUS_DRAFT)
        self.assertEqual(plan.outfits.count(), 0)

    @patch("planner.services.fetch_week_weather")
    @patch("planner.services.Garment.objects.filter")
    @patch("planner.services.OpenAI")
    @patch("planner.services.OutfitItem.objects.create")
    def test_invalid_garment_ids_do_not_create_empty_outfits(
        self,
        mock_outfit_item,
        mock_openai,
        mock_garment_filter,
        mock_weather,
    ):
        plan = self.create_plan()
        forecasts = self.create_mock_forecasts()

        mock_weather.return_value = forecasts
        mock_garment_filter.return_value = [self.create_mock_garment()]
        self.configure_openai_response(
            mock_openai,
            self.create_ai_response(forecasts, garment_ids=[999]),
        )

        with self.assertRaises(ValueError):
            generate_outfits(plan)

        plan.refresh_from_db()

        self.assertEqual(plan.status, WeeklyPlan.STATUS_DRAFT)
        self.assertEqual(plan.outfits.count(), 0)
        mock_outfit_item.assert_not_called()

    @patch("planner.views.generate_outfits")
    def test_generation_error_sets_plan_to_failed(self, mock_generate):
        self.create_plan()
        mock_generate.side_effect = Exception("Test generation error")
        self.client.force_login(self.user)

        response = self.client.post(
            "/planner/create/",
            {
                "week_start": "2026-10-12",
                "city": "Baku",
                "preferred_formality": "casual",
                "notes": "Test",
            },
        )

        self.assertEqual(response.status_code, 302)

        failed_plan = WeeklyPlan.objects.get(
            user=self.user,
            week_start="2026-10-12",
        )
        self.assertEqual(failed_plan.status, WeeklyPlan.STATUS_FAILED)

    @patch("planner.views.generate_outfits")
    def test_weather_failure_shows_fallback_modal(self, mock_generate):
        mock_generate.side_effect = WeatherUnavailableError(
            "Reliable weather data is currently unavailable."
        )
        self.client.force_login(self.user)

        response = self.client.post(
            "/planner/create/",
            {
                "week_start": "2026-10-12",
                "city": "Baku",
                "preferred_formality": "casual",
                "notes": "Test",
                "use_estimated_weather": "0",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.context["show_weather_fallback_modal"]
        )

        plan = WeeklyPlan.objects.get(
            user=self.user,
            week_start="2026-10-12",
        )
        self.assertEqual(plan.status, WeeklyPlan.STATUS_DRAFT)

    def test_user_cannot_access_another_users_plan(self):
        second_user = User.objects.create_user(
            email="second@example.com",
            password="testpassword123",
        )

        plan = WeeklyPlan.objects.create(
            user=second_user,
            week_start="2026-10-12",
            city="Baku",
            preferred_formality="casual",
        )

        self.client.force_login(self.user)
        response = self.client.get(f"/planner/weekly/{plan.pk}/")

        self.assertEqual(response.status_code, 404)
