import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from .forms import GarmentUploadForm
from .models import Garment, GarmentAnalysis
from .services import save_garment_analysis


User = get_user_model()


class GarmentTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpassword123",
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpassword123",
        )

    def create_image(
        self,
        name="shirt.jpg",
        image_format="JPEG",
    ):
        image = Image.new(
            "RGB",
            (100, 100),
            "white",
        )

        output = io.BytesIO()

        image.save(
            output,
            format=image_format,
        )

        content_type_map = {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "WEBP": "image/webp",
        }

        return SimpleUploadedFile(
            name,
            output.getvalue(),
            content_type=content_type_map[image_format],
        )

    def create_garment(
        self,
        user=None,
        name="White Shirt",
        status=Garment.STATUS_AVAILABLE,
        ai_analyzed=False,
    ):
        if user is None:
            user = self.user

        return Garment.objects.create(
            user=user,
            name=name,
            image=self.create_image(),
            category=Garment.CATEGORY_TOP,
            color="white",
            formality=Garment.FORMALITY_CASUAL,
            status=status,
            ai_analyzed=ai_analyzed,
        )

    def test_garment_can_be_created(self):
        garment = self.create_garment()

        self.assertEqual(
            garment.name,
            "White Shirt",
        )

        self.assertEqual(
            garment.user,
            self.user,
        )

    def test_garment_default_status_is_available(self):
        garment = Garment.objects.create(
            user=self.user,
            name="Black T-Shirt",
            image=self.create_image("black.jpg"),
        )

        self.assertEqual(
            garment.status,
            Garment.STATUS_AVAILABLE,
        )

    def test_garment_default_category_is_other(self):
        garment = Garment.objects.create(
            user=self.user,
            name="Unknown Item",
            image=self.create_image("item.jpg"),
        )

        self.assertEqual(
            garment.category,
            Garment.CATEGORY_OTHER,
        )

    def test_garment_default_formality_is_casual(self):
        garment = Garment.objects.create(
            user=self.user,
            name="Basic Shirt",
            image=self.create_image("basic.jpg"),
        )

        self.assertEqual(
            garment.formality,
            Garment.FORMALITY_CASUAL,
        )

    def test_garment_ai_analyzed_defaults_to_false(self):
        garment = self.create_garment()

        self.assertFalse(
            garment.ai_analyzed
        )

    def test_garment_can_be_marked_unavailable(self):
        garment = self.create_garment(
            status=Garment.STATUS_UNAVAILABLE
        )

        self.assertEqual(
            garment.status,
            Garment.STATUS_UNAVAILABLE,
        )

    def test_garment_can_be_archived(self):
        garment = self.create_garment(
            status=Garment.STATUS_ARCHIVED
        )

        self.assertEqual(
            garment.status,
            Garment.STATUS_ARCHIVED,
        )

    def test_different_users_can_have_garments_with_same_name(self):
        garment1 = self.create_garment(
            user=self.user,
            name="White Shirt",
        )

        garment2 = self.create_garment(
            user=self.other_user,
            name="White Shirt",
        )

        self.assertNotEqual(
            garment1.user,
            garment2.user,
        )

        self.assertEqual(
            garment1.name,
            garment2.name,
        )

    def test_garment_analysis_can_be_created(self):
        garment = self.create_garment()

        analysis = GarmentAnalysis.objects.create(
            garment=garment,
            raw_response={
                "name": "White Shirt",
                "category": "top",
                "color": "white",
                "confidence": 0.95,
            },
            model_name="gpt-6-luna",
        )

        self.assertEqual(
            analysis.garment,
            garment,
        )

        self.assertEqual(
            analysis.model_name,
            "gpt-6-luna",
        )

        self.assertEqual(
            analysis.raw_response["category"],
            "top",
        )

    def test_garment_analysis_is_one_to_one(self):
        garment = self.create_garment()

        GarmentAnalysis.objects.create(
            garment=garment,
            raw_response={
                "category": "top"
            },
            model_name="gpt-6-luna",
        )

        analysis = GarmentAnalysis.objects.get(
            garment=garment
        )

        self.assertEqual(
            analysis.garment,
            garment,
        )

    def test_save_garment_analysis_updates_garment(self):
        garment = self.create_garment()

        data = {
            "name": "Blue Shirt",
            "category": "top",
            "color": "blue",
            "secondary_colors": ["white"],
            "material": "cotton",
            "pattern": "striped",
            "formality": "casual",
            "season": "spring",
            "weather_suitability": [
                "mild",
                "warm",
            ],
            "description": "Blue striped cotton shirt.",
            "confidence": 0.94,
        }

        with patch(
            "wardrobe.services.settings.OPENAI_MODEL",
            "gpt-6-luna",
        ):
            save_garment_analysis(
                garment,
                data,
            )

        garment.refresh_from_db()

        self.assertEqual(
            garment.name,
            "Blue Shirt",
        )

        self.assertEqual(
            garment.category,
            Garment.CATEGORY_TOP,
        )

        self.assertEqual(
            garment.color,
            "blue",
        )

        self.assertEqual(
            garment.material,
            "cotton",
        )

        self.assertEqual(
            garment.pattern,
            "striped",
        )

        self.assertTrue(
            garment.ai_analyzed
        )

        self.assertEqual(
            garment.ai_confidence,
            0.94,
        )

        self.assertTrue(
            GarmentAnalysis.objects.filter(
                garment=garment
            ).exists()
        )

    def test_invalid_category_becomes_other(self):
        garment = self.create_garment()

        data = {
            "name": "Test Garment",
            "category": "invalid_category",
            "formality": "casual",
            "confidence": 0.8,
        }

        with patch(
            "wardrobe.services.settings.OPENAI_MODEL",
            "gpt-6-luna",
        ):
            save_garment_analysis(
                garment,
                data,
            )

        garment.refresh_from_db()

        self.assertEqual(
            garment.category,
            Garment.CATEGORY_OTHER,
        )

    def test_invalid_formality_becomes_other(self):
        garment = self.create_garment()

        data = {
            "name": "Test Garment",
            "category": "top",
            "formality": "invalid_formality",
            "confidence": 0.8,
        }

        with patch(
            "wardrobe.services.settings.OPENAI_MODEL",
            "gpt-6-luna",
        ):
            save_garment_analysis(
                garment,
                data,
            )

        garment.refresh_from_db()

        self.assertEqual(
            garment.formality,
            Garment.FORMALITY_OTHER,
        )

    def test_confidence_is_limited_to_one(self):
        garment = self.create_garment()

        data = {
            "name": "Test Garment",
            "category": "top",
            "formality": "casual",
            "confidence": 1.5,
        }

        with patch(
            "wardrobe.services.settings.OPENAI_MODEL",
            "gpt-6-luna",
        ):
            save_garment_analysis(
                garment,
                data,
            )

        garment.refresh_from_db()

        self.assertEqual(
            garment.ai_confidence,
            1.0,
        )

    def test_negative_confidence_becomes_zero(self):
        garment = self.create_garment()

        data = {
            "name": "Test Garment",
            "category": "top",
            "formality": "casual",
            "confidence": -0.5,
        }

        with patch(
            "wardrobe.services.settings.OPENAI_MODEL",
            "gpt-6-luna",
        ):
            save_garment_analysis(
                garment,
                data,
            )

        garment.refresh_from_db()

        self.assertEqual(
            garment.ai_confidence,
            0.0,
        )

    def test_upload_form_accepts_valid_image(self):
        image = self.create_image()

        form = GarmentUploadForm(
            files={
                "images": [image]
            }
        )

        self.assertTrue(
            form.is_valid(),
            form.errors,
        )

    def test_upload_form_accepts_png(self):
        image = self.create_image(
            name="shirt.png",
            image_format="PNG",
        )

        form = GarmentUploadForm(
            files={
                "images": [image]
            }
        )

        self.assertTrue(
            form.is_valid(),
            form.errors,
        )

    def test_upload_form_accepts_webp(self):
        image = self.create_image(
            name="shirt.webp",
            image_format="WEBP",
        )

        form = GarmentUploadForm(
            files={
                "images": [image]
            }
        )

        self.assertTrue(
            form.is_valid(),
            form.errors,
        )

    def test_upload_form_rejects_too_many_images(self):
        images = [
            self.create_image(
                f"shirt{i}.jpg"
            )
            for i in range(11)
        ]

        form = GarmentUploadForm(
            files={
                "images": images
            }
        )

        self.assertFalse(
            form.is_valid()
        )

    def test_upload_form_rejects_invalid_file_type(self):
        file = SimpleUploadedFile(
            "test.txt",
            b"not an image",
            content_type="text/plain",
        )

        form = GarmentUploadForm(
            files={
                "images": [file]
            }
        )

        self.assertFalse(
            form.is_valid()
        )

    def test_garment_detail_is_protected_between_users(self):
        garment = self.create_garment(
            user=self.other_user
        )

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            f"/wardrobe/{garment.pk}/"
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_garment_archive_is_protected_between_users(self):
        garment = self.create_garment(
            user=self.other_user
        )

        self.client.force_login(
            self.user
        )

        response = self.client.post(
            f"/wardrobe/{garment.pk}/archive/"
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        garment.refresh_from_db()

        self.assertEqual(
            garment.status,
            Garment.STATUS_AVAILABLE,
        )

    def test_garment_toggle_availability_is_protected_between_users(self):
        garment = self.create_garment(
            user=self.other_user
        )

        self.client.force_login(
            self.user
        )

        response = self.client.post(
            f"/wardrobe/{garment.pk}/availability/"
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        garment.refresh_from_db()

        self.assertEqual(
            garment.status,
            Garment.STATUS_AVAILABLE,
        )

    @patch("wardrobe.views.analyze_garment_image")
    def test_garment_upload_saves_ai_analysis(
        self,
        mock_analyze,
    ):
        self.client.force_login(
            self.user
        )

        mock_analyze.return_value = {
            "name": "Blue Shirt",
            "category": "top",
            "color": "blue",
            "secondary_colors": [],
            "material": "cotton",
            "pattern": "plain",
            "formality": "casual",
            "season": "all",
            "weather_suitability": [
                "mild"
            ],
            "description": "Blue cotton shirt.",
            "confidence": 0.95,
        }

        image = self.create_image(
            "blue_shirt.jpg"
        )

        response = self.client.post(
            "/wardrobe/upload/",
            {
                "images": [image]
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        garment = Garment.objects.get(
            user=self.user
        )

        self.assertEqual(
            garment.name,
            "Blue Shirt",
        )

        self.assertTrue(
            garment.ai_analyzed
        )

        self.assertTrue(
            GarmentAnalysis.objects.filter(
                garment=garment
            ).exists()
        )

        mock_analyze.assert_called_once()

    @patch("wardrobe.views.analyze_garment_image")
    def test_garment_upload_handles_ai_error(
        self,
        mock_analyze,
    ):
        self.client.force_login(
            self.user
        )

        mock_analyze.side_effect = Exception(
            "Test AI error"
        )

        image = self.create_image(
            "error.jpg"
        )

        response = self.client.post(
            "/wardrobe/upload/",
            {
                "images": [image]
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            Garment.objects.filter(
                user=self.user
            ).count(),
            0,
        )

    def test_garment_list_requires_login(self):
        response = self.client.get(
            "/wardrobe/"
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_garment_detail_requires_login(self):
        garment = self.create_garment()

        response = self.client.get(
            f"/wardrobe/{garment.pk}/"
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_garment_list_shows_only_current_users_garments(self):
        self.create_garment(
            user=self.user,
            name="My Shirt",
        )

        self.create_garment(
            user=self.other_user,
            name="Other Shirt",
        )

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            "/wardrobe/"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "My Shirt",
        )

        self.assertNotContains(
            response,
            "Other Shirt",
        )