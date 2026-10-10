
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import WeeklyPlanForm
from .models import Outfit, WeeklyPlan
from .services import generate_outfits


def get_week_starts():
    today = timezone.localdate()

    current_week_start = (
        today
        - timedelta(days=today.weekday())
    )

    next_week_start = (
        current_week_start
        + timedelta(days=7)
    )

    return (
        today,
        current_week_start,
        next_week_start,
    )


def get_allowed_week_start(selected_week):
    _, current_week_start, next_week_start = (
        get_week_starts()
    )

    if selected_week == "next":
        return next_week_start

    return current_week_start


def delete_expired_outfits(user):
    today = timezone.localdate()

    Outfit.objects.filter(
        weekly_plan__user=user,
        date__lt=today,
    ).delete()


@login_required
def create_plan(request):
    delete_expired_outfits(request.user)

    if request.method == "POST":
        form = WeeklyPlanForm(request.POST)

        if form.is_valid():
            plan = form.save(commit=False)
            plan.user = request.user
            plan.status = WeeklyPlan.STATUS_DRAFT

            try:
                existing_plan = WeeklyPlan.objects.get(
                    user=request.user,
                    week_start=plan.week_start,
                )

                if (
                    existing_plan.status
                    == WeeklyPlan.STATUS_GENERATED
                ):
                    messages.info(
                        request,
                        "You already have a plan for this week.",
                    )

                    return redirect(
                        "planner:weekly",
                        pk=existing_plan.pk,
                    )

                existing_plan.city = plan.city
                existing_plan.notes = plan.notes
                existing_plan.status = WeeklyPlan.STATUS_DRAFT
                existing_plan.save(
                    update_fields=[
                        "city",
                        "notes",
                        "status",
                        "updated_at",
                    ]
                )

                plan = existing_plan

            except WeeklyPlan.DoesNotExist:
                try:
                    plan.save()

                except IntegrityError:
                    messages.error(
                        request,
                        "You already have a plan for this week.",
                    )

                    return redirect("planner:create")

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

            except Exception:
                plan.status = WeeklyPlan.STATUS_FAILED
                plan.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

                messages.error(
                    request,
                    "Could not generate outfits. Please check "
                    "your wardrobe and try again.",
                )

                return redirect("planner:create")

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
def current_week(request):
    delete_expired_outfits(request.user)

    (
        today,
        current_week_start,
        next_week_start,
    ) = get_week_starts()

    selected_week = request.GET.get(
        "week",
        "current",
    )

    if selected_week not in {"current", "next"}:
        selected_week = "current"

    selected_week_start = get_allowed_week_start(
        selected_week
    )

    week_end = selected_week_start + timedelta(days=6)

    plan = (
        WeeklyPlan.objects
        .filter(
            user=request.user,
            week_start=selected_week_start,
            status=WeeklyPlan.STATUS_GENERATED,
        )
        .prefetch_related("outfits__items__garment")
        .first()
    )

    is_current_week = selected_week == "current"

    return render(
        request,
        "planner/current.html",
        {
            "plan": plan,
            "week_end": week_end,
            "selected_week": selected_week,
            "is_current_week": is_current_week,
            "has_plan": plan is not None,
            "today": today,
            "current_week_start": current_week_start,
            "next_week_start": next_week_start,
        },
    )


@login_required
def weekly_plan(request, pk):
    delete_expired_outfits(request.user)

    plan = get_object_or_404(
        WeeklyPlan.objects.prefetch_related(
            "outfits__items__garment"
        ),
        pk=pk,
        user=request.user,
    )

    (
        today,
        current_week_start,
        next_week_start,
    ) = get_week_starts()

    allowed_week_starts = {
        current_week_start,
        next_week_start,
    }

    if (
        plan.week_start not in allowed_week_starts
        or plan.status != WeeklyPlan.STATUS_GENERATED
    ):
        messages.info(
            request,
            "This weekly outfit plan is no longer available.",
        )

        return redirect("planner:current")

    week_end = plan.week_start + timedelta(days=6)

    selected_week = (
        "current"
        if plan.week_start == current_week_start
        else "next"
    )

    return render(
        request,
        "planner/weekly.html",
        {
            "plan": plan,
            "week_end": week_end,
            "selected_week": selected_week,
        },
    )
