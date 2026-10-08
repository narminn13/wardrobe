from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import WeeklyPlan


class WeeklyPlanForm(forms.ModelForm):
    class Meta:
        model = WeeklyPlan
        fields = [
            "week_start",
            "city",
            "notes",
        ]

        widgets = {
            "week_start": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control",
                }
            ),
            "city": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Baku",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Optional preferences...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        today = timezone.localdate()

        current_week_start = (
            today
            - timedelta(days=today.weekday())
        )

        next_week_start = (
            current_week_start
            + timedelta(days=7)
        )

        next_week_end = (
            next_week_start
            + timedelta(days=6)
        )

        self.fields["week_start"].widget.attrs.update(
            {
                "min": current_week_start.isoformat(),
                "max": next_week_end.isoformat(),
            }
        )

    def clean_week_start(self):
        selected_date = self.cleaned_data["week_start"]

        today = timezone.localdate()

        current_week_start = (
            today
            - timedelta(days=today.weekday())
        )

        current_week_end = (
            current_week_start
            + timedelta(days=6)
        )

        next_week_start = (
            current_week_start
            + timedelta(days=7)
        )

        next_week_end = (
            next_week_start
            + timedelta(days=6)
        )

        if selected_date < current_week_start:
            raise forms.ValidationError(
                "You can only create plans for the current "
                "or next week."
            )

        if selected_date > next_week_end:
            raise forms.ValidationError(
                "You can only create plans for the current "
                "or next week."
            )

        if selected_date <= current_week_end:
            return current_week_start

        return next_week_start