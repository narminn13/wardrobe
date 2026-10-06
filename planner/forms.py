from django import forms

from .models import WeeklyPlan


class WeeklyPlanForm(forms.ModelForm):
    class Meta:
        model = WeeklyPlan
        fields = [
            "week_start",
            "city",
            "preferred_formality",
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
            "preferred_formality": forms.Select(
                attrs={
                    "class": "form-select",
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

        self.fields["preferred_formality"].required = False
        self.fields["preferred_formality"].initial = "casual"