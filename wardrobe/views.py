from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import GarmentUploadForm
from .models import Garment
from .services import analyze_garment_image, save_garment_analysis


@login_required
def garment_list(request):
    garments = Garment.objects.filter(
        user=request.user
    ).select_related("user")

    return render(
        request,
        "wardrobe/list.html",
        {"garments": garments},
    )


@login_required
def garment_upload(request):
    if request.method == "POST":
        form = GarmentUploadForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            files = form.cleaned_data["images"]
            success_count = 0

            for file in files:
                try:
                    with transaction.atomic():
                        garment = Garment.objects.create(
                            user=request.user,
                            name=file.name.rsplit(
                                ".",
                                1,
                            )[0][:150],
                            image=file,
                        )

                        data = analyze_garment_image(file)

                        save_garment_analysis(
                            garment,
                            data,
                        )

                        success_count += 1

                except Exception:
                    messages.error(
                        request,
                        f"{file.name} could not be analyzed.",
                    )

            if success_count:
                messages.success(
                    request,
                    f"{success_count} garment(s) added successfully.",
                )

            return redirect(
                "wardrobe:list"
            )

        messages.error(
            request,
            "Please correct the errors below.",
        )

    else:
        form = GarmentUploadForm()

    return render(
        request,
        "wardrobe/upload.html",
        {"form": form},
    )


@login_required
def garment_detail(request, pk):
    garment = get_object_or_404(
        Garment,
        pk=pk,
        user=request.user,
    )

    return render(
        request,
        "wardrobe/detail.html",
        {"garment": garment},
    )


@login_required
def garment_archive(request, pk):
    garment = get_object_or_404(
        Garment,
        pk=pk,
        user=request.user,
    )

    if request.method == "POST":
        garment.status = Garment.STATUS_ARCHIVED

        garment.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        messages.success(
            request,
            "Garment archived.",
        )

    return redirect(
        "wardrobe:list"
    )


@login_required
def garment_toggle_availability(request, pk):
    garment = get_object_or_404(
        Garment,
        pk=pk,
        user=request.user,
    )

    if request.method == "POST":
        if garment.status == Garment.STATUS_AVAILABLE:
            garment.status = Garment.STATUS_UNAVAILABLE
        else:
            garment.status = Garment.STATUS_AVAILABLE

        garment.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

    return redirect(
        "wardrobe:detail",
        pk=garment.pk,
    )