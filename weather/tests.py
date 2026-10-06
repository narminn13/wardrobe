from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import WeatherForecast
from .services import (
    fetch_week_weather,
    get_city_coordinates,
    weather_description,
)


User = get_user_model()


class WeatherTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpassword123",
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpassword123",
        )

    def test_weather_forecast_can_be_created(self):
        forecast = WeatherForecast.objects.create(
            user=self.user,
            date=timezone.localdate(),
            latitude=40.4093,
            longitude=49.8671,
            temperature_min=15.0,
            temperature_max=25.0,
            precipitation_probability=20,
            rain=False,
            wind_speed=12.0,
            weather_code=0,
            raw_data={
                "description": "Clear sky"
            },
        )

        self.assertEqual(
            forecast.user,
            self.user,
        )

        self.assertEqual(
            forecast.temperature_min,
            15.0,
        )

        self.assertEqual(
            forecast.temperature_max,
            25.0,
        )

    def test_weather_description_known_code(self):
        self.assertEqual(
            weather_description(0),
            "Clear sky",
        )

        self.assertEqual(
            weather_description(61),
            "Slight rain",
        )

        self.assertEqual(
            weather_description(71),
            "Slight snow",
        )

        self.assertEqual(
            weather_description(95),
            "Thunderstorm",
        )

    def test_weather_description_unknown_code(self):
        self.assertEqual(
            weather_description(999),
            "Unknown",
        )

    @patch("weather.services.requests.get")
    def test_get_city_coordinates_returns_coordinates(
        self,
        mock_get,
    ):
        response = Mock()

        response.json.return_value = {
            "results": [
                {
                    "latitude": 40.4093,
                    "longitude": 49.8671,
                }
            ]
        }

        response.raise_for_status.return_value = None

        mock_get.return_value = response

        latitude, longitude = get_city_coordinates(
            "Baku"
        )

        self.assertEqual(
            latitude,
            40.4093,
        )

        self.assertEqual(
            longitude,
            49.8671,
        )

        mock_get.assert_called_once()

    @patch("weather.services.requests.get")
    def test_get_city_coordinates_raises_when_city_not_found(
        self,
        mock_get,
    ):
        response = Mock()

        response.json.return_value = {
            "results": []
        }

        response.raise_for_status.return_value = None

        mock_get.return_value = response

        with self.assertRaisesMessage(
            ValueError,
            "Could not find the city: UnknownCity",
        ):
            get_city_coordinates(
                "UnknownCity"
            )

    @patch("weather.services.requests.get")
    def test_get_city_coordinates_raises_for_http_error(
        self,
        mock_get,
    ):
        response = Mock()

        response.raise_for_status.side_effect = Exception(
            "API error"
        )

        mock_get.return_value = response

        with self.assertRaises(Exception):
            get_city_coordinates(
                "Baku"
            )

    @patch("weather.services.get_city_coordinates")
    @patch("weather.services.requests.get")
    def test_fetch_week_weather_creates_forecasts(
        self,
        mock_get,
        mock_coordinates,
    ):
        mock_coordinates.return_value = (
            40.4093,
            49.8671,
        )

        today = timezone.localdate()

        dates = [
            str(today + timedelta(days=i))
            for i in range(7)
        ]

        response = Mock()

        response.raise_for_status.return_value = None

        response.json.return_value = {
            "daily": {
                "time": dates,
                "weather_code": [
                    0,
                    1,
                    2,
                    3,
                    61,
                    63,
                    71,
                ],
                "temperature_2m_max": [
                    25,
                    26,
                    27,
                    24,
                    20,
                    18,
                    10,
                ],
                "temperature_2m_min": [
                    15,
                    16,
                    17,
                    14,
                    12,
                    10,
                    3,
                ],
                "precipitation_probability_max": [
                    0,
                    10,
                    20,
                    30,
                    60,
                    80,
                    90,
                ],
                "rain_sum": [
                    0,
                    0,
                    0,
                    0,
                    2.5,
                    5.0,
                    4.0,
                ],
                "wind_speed_10m_max": [
                    10,
                    12,
                    14,
                    15,
                    20,
                    22,
                    25,
                ],
            }
        }

        mock_get.return_value = response

        forecasts = fetch_week_weather(
            self.user,
            "Baku",
        )

        self.assertEqual(
            len(forecasts),
            7,
        )

        self.assertEqual(
            WeatherForecast.objects.filter(
                user=self.user
            ).count(),
            7,
        )

        first_forecast = forecasts[0]

        self.assertEqual(
            first_forecast.user,
            self.user,
        )

        self.assertEqual(
            str(first_forecast.date),
            str(today),
        )

        self.assertEqual(
            first_forecast.temperature_min,
            15,
        )

        self.assertEqual(
            first_forecast.temperature_max,
            25,
        )

        self.assertFalse(
            first_forecast.rain
        )

        self.assertEqual(
            first_forecast.weather_code,
            0,
        )

        self.assertEqual(
            first_forecast.raw_data["description"],
            "Clear sky",
        )

    @patch("weather.services.get_city_coordinates")
    @patch("weather.services.requests.get")
    def test_fetch_week_weather_marks_rain_correctly(
        self,
        mock_get,
        mock_coordinates,
    ):
        mock_coordinates.return_value = (
            40.4093,
            49.8671,
        )

        today = timezone.localdate()

        dates = [
            str(today + timedelta(days=i))
            for i in range(7)
        ]

        response = Mock()

        response.raise_for_status.return_value = None

        response.json.return_value = {
            "daily": {
                "time": dates,
                "weather_code": [
                    0,
                    61,
                    63,
                    65,
                    0,
                    0,
                    0,
                ],
                "temperature_2m_max": [
                    25,
                    20,
                    19,
                    18,
                    24,
                    25,
                    26,
                ],
                "temperature_2m_min": [
                    15,
                    12,
                    11,
                    10,
                    14,
                    15,
                    16,
                ],
                "precipitation_probability_max": [
                    0,
                    50,
                    70,
                    90,
                    0,
                    0,
                    0,
                ],
                "rain_sum": [
                    0,
                    1.0,
                    3.0,
                    8.0,
                    0,
                    0,
                    0,
                ],
                "wind_speed_10m_max": [
                    10,
                    15,
                    20,
                    25,
                    10,
                    12,
                    14,
                ],
            }
        }

        mock_get.return_value = response

        forecasts = fetch_week_weather(
            self.user,
            "Baku",
        )

        self.assertFalse(
            forecasts[0].rain
        )

        self.assertTrue(
            forecasts[1].rain
        )

        self.assertTrue(
            forecasts[2].rain
        )

        self.assertTrue(
            forecasts[3].rain
        )

    @patch("weather.services.get_city_coordinates")
    @patch("weather.services.requests.get")
    def test_fetch_week_weather_saves_weather_description(
        self,
        mock_get,
        mock_coordinates,
    ):
        mock_coordinates.return_value = (
            40.4093,
            49.8671,
        )

        today = timezone.localdate()

        dates = [
            str(today + timedelta(days=i))
            for i in range(7)
        ]

        response = Mock()

        response.raise_for_status.return_value = None

        response.json.return_value = {
            "daily": {
                "time": dates,
                "weather_code": [
                    0,
                    61,
                    71,
                    95,
                    3,
                    45,
                    80,
                ],
                "temperature_2m_max": [25] * 7,
                "temperature_2m_min": [15] * 7,
                "precipitation_probability_max": [10] * 7,
                "rain_sum": [0] * 7,
                "wind_speed_10m_max": [10] * 7,
            }
        }

        mock_get.return_value = response

        forecasts = fetch_week_weather(
            self.user,
            "Baku",
        )

        self.assertEqual(
            forecasts[0].raw_data["description"],
            "Clear sky",
        )

        self.assertEqual(
            forecasts[1].raw_data["description"],
            "Slight rain",
        )

        self.assertEqual(
            forecasts[2].raw_data["description"],
            "Slight snow",
        )

        self.assertEqual(
            forecasts[3].raw_data["description"],
            "Thunderstorm",
        )

    def test_fetch_week_weather_requires_city(self):
        with self.assertRaisesMessage(
            ValueError,
            "City is required for weather forecast.",
        ):
            fetch_week_weather(
                self.user,
                "",
            )

    @patch("weather.services.get_city_coordinates")
    @patch("weather.services.requests.get")
    def test_fetch_week_weather_raises_when_no_dates_returned(
        self,
        mock_get,
        mock_coordinates,
    ):
        mock_coordinates.return_value = (
            40.4093,
            49.8671,
        )

        response = Mock()

        response.raise_for_status.return_value = None

        response.json.return_value = {
            "daily": {
                "time": [],
            }
        }

        mock_get.return_value = response

        with self.assertRaisesMessage(
            ValueError,
            "Weather API returned no forecast data.",
        ):
            fetch_week_weather(
                self.user,
                "Baku",
            )

    @patch("weather.services.get_city_coordinates")
    @patch("weather.services.requests.get")
    def test_fetch_week_weather_deletes_old_forecasts(
        self,
        mock_get,
        mock_coordinates,
    ):
        mock_coordinates.return_value = (
            40.4093,
            49.8671,
        )

        today = timezone.localdate()

        old_forecast = WeatherForecast.objects.create(
            user=self.user,
            date=today + timedelta(days=2),
            latitude=40.4093,
            longitude=49.8671,
            temperature_min=10,
            temperature_max=20,
            precipitation_probability=20,
            rain=False,
            wind_speed=10,
            weather_code=0,
            raw_data={
                "description": "Old forecast"
            },
        )

        old_forecast_id = old_forecast.pk

        response = Mock()

        response.raise_for_status.return_value = None

        dates = [
            str(today + timedelta(days=i))
            for i in range(7)
        ]

        response.json.return_value = {
            "daily": {
                "time": dates,
                "weather_code": [0] * 7,
                "temperature_2m_max": [25] * 7,
                "temperature_2m_min": [15] * 7,
                "precipitation_probability_max": [0] * 7,
                "rain_sum": [0] * 7,
                "wind_speed_10m_max": [10] * 7,
            }
        }

        mock_get.return_value = response

        fetch_week_weather(
            self.user,
            "Baku",
        )

        self.assertFalse(
            WeatherForecast.objects.filter(
                pk=old_forecast_id
            ).exists()
        )

        self.assertEqual(
            WeatherForecast.objects.filter(
                user=self.user
            ).count(),
            7,
        )

    @patch("weather.services.get_city_coordinates")
    @patch("weather.services.requests.get")
    def test_fetch_week_weather_does_not_delete_other_users_forecasts(
        self,
        mock_get,
        mock_coordinates,
    ):
        mock_coordinates.return_value = (
            40.4093,
            49.8671,
        )

        today = timezone.localdate()

        other_forecast = WeatherForecast.objects.create(
            user=self.other_user,
            date=today,
            latitude=40.4093,
            longitude=49.8671,
            temperature_min=10,
            temperature_max=20,
            precipitation_probability=20,
            rain=False,
            wind_speed=10,
            weather_code=0,
            raw_data={
                "description": "Other user's forecast"
            },
        )

        response = Mock()

        response.raise_for_status.return_value = None

        dates = [
            str(today + timedelta(days=i))
            for i in range(7)
        ]

        response.json.return_value = {
            "daily": {
                "time": dates,
                "weather_code": [0] * 7,
                "temperature_2m_max": [25] * 7,
                "temperature_2m_min": [15] * 7,
                "precipitation_probability_max": [0] * 7,
                "rain_sum": [0] * 7,
                "wind_speed_10m_max": [10] * 7,
            }
        }

        mock_get.return_value = response

        fetch_week_weather(
            self.user,
            "Baku",
        )

        other_forecast.refresh_from_db()

        self.assertEqual(
            other_forecast.raw_data["description"],
            "Other user's forecast",
        )

        self.assertEqual(
            WeatherForecast.objects.filter(
                user=self.other_user
            ).count(),
            1,
        )