from django import forms


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            raise forms.ValidationError(
                "Please select at least one image."
            )

        if not isinstance(data, (list, tuple)):
            data = [data]

        cleaned_files = []

        allowed_types = {
            "image/jpeg",
            "image/png",
            "image/webp",
        }

        max_size = 8 * 1024 * 1024

        if len(data) > 5:
            raise forms.ValidationError(
                "You can upload a maximum of 5 images at once."
            )

        for file in data:
            if file.content_type not in allowed_types:
                raise forms.ValidationError(
                    f"{file.name} is not a supported image."
                )

            if file.size > max_size:
                raise forms.ValidationError(
                    f"{file.name} is larger than 8 MB."
                )

            cleaned_files.append(file)

        return cleaned_files


class GarmentUploadForm(forms.Form):
    images = MultipleFileField(
        widget=MultipleFileInput(
            attrs={
                "class": "form-control",
                "accept": "image/jpeg,image/png,image/webp",
                "multiple": True,
            }
        )
    )