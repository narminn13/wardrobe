from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render

from .forms import WeeklyPlanForm
from .models import WeeklyPlan
from .services import generate_outfits


@login_required
def create_plan(request):
    if request.method == "POST":
        form = WeeklyPlanForm(request.POST)

        if form.is_valid():
            plan = form.save(
                commit=False
            )

            plan.user = request.user
            plan.status = WeeklyPlan.STATUS_DRAFT

            try:
                plan.save()

            except IntegrityError:
                messages.error(
                    request,
                    "You already have a plan for this week.",
                )

                return redirect(
                    "planner:create"
                )

            try:
                generate_outfits(plan)

                messages.success(
                    request,
                    "Your weekly outfits have been generated.",
                )

                return redirect(
                    "planner:weekly",
                    pk=plan.pk,
                )

            except Exception as exc:
                plan.status = WeeklyPlan.STATUS_FAILED

                plan.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

                messages.error(
                    request,
                    f"Could not generate outfits: {exc}",
                )

                return redirect(
                    "planner:create"
                )

        messages.error(
            request,
            "Please correct the errors below.",
        )

    else:
        form = WeeklyPlanForm()

    return render(
        request,
        "planner/create.html",
        {"form": form},
    )


@login_required
def weekly_plan(request, pk):
    plan = get_object_or_404(
        WeeklyPlan.objects.prefetch_related(
            "outfits__items__garment"
        ),
        pk=pk,
        user=request.user,
    )

    return render(
        request,
        "planner/weekly.html",
        {"plan": plan},
    )