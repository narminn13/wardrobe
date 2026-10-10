
import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import WeeklyPlanForm
from .models import Outfit, WeeklyPlan
from .services import delete_expired_outfits, generate_outfits

logger = logging.getLogger(__name__)


def get_week_starts():
    today = timezone.localdate()
    current_week_start = today - timedelta(days=today.weekday())
    next_week_start = current_week_start + timedelta(days=7)

    return today, current_week_start, next_week_start


def get_allowed_week_start(selected_week):
    _, current_week_start, next_week_start = get_week_starts()

    return (
        next_week_start
        if selected_week == "next"
        else current_week_start
    )


@login_required
def create_plan(request):
    delete_expired_outfits(request.user)

    if request.method != "POST":
        return render(
            request,
            "planner/create.html",
            {"form": WeeklyPlanForm()},
        )

    form = WeeklyPlanForm(request.POST)

    if not form.is_valid():
        messages.error(request, "Please correct the errors below.")
        return render(
            request,
            "planner/create.html",
            {"form": form},
        )

    plan = form.save(commit=False)
    plan.user = request.user

    try:
        existing_plan = WeeklyPlan.objects.filter(
            user=request.user,
            week_start=plan.week_start,
        ).first()

        if (
            existing_plan
            and existing_plan.status == WeeklyPlan.STATUS_GENERATED
        ):
            messages.info(
                request,
                "You already have a generated plan for this week.",
            )
            return redirect("planner:weekly", pk=existing_plan.pk)

        if existing_plan:
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
        else:
            plan.status = WeeklyPlan.STATUS_DRAFT
            plan.save()

    except IntegrityError:
        logger.exception("Could not save the weekly plan.")
        messages.error(
            request,
            "Could not save your plan. Please try again.",
        )
        return redirect("planner:create")

    try:
        generate_outfits(plan)
    except Exception:
        logger.exception(
            "Outfit generation failed for plan %s",
            plan.pk,
        )

        plan.status = WeeklyPlan.STATUS_FAILED
        plan.save(
            update_fields=["status", "updated_at"]
        )

        messages.error(
            request,
            "Outfit generation failed. Please try again. "
            "If the problem continues, check the application logs.",
        )
        return redirect("planner:create")

    messages.success(
        request,
        "Your weekly outfits have been generated.",
    )
    return redirect("planner:weekly", pk=plan.pk)


@login_required
def current_week(request):
    delete_expired_outfits(request.user)

    (
        today,
        current_week_start,
        next_week_start,
    ) = get_week_starts()

    selected_week = request.GET.get("week", "current")

    if selected_week not in {"current", "next"}:
        selected_week = "current"

    selected_week_start = (
        next_week_start
        if selected_week == "next"
        else current_week_start
    )
    week_end = selected_week_start + timedelta(days=6)

    plan = WeeklyPlan.objects.filter(
        user=request.user,
        week_start=selected_week_start,
        status=WeeklyPlan.STATUS_GENERATED,
    ).first()

    outfits = Outfit.objects.none()

    if plan:
        outfit_start = (
            today
            if selected_week == "current"
            else selected_week_start
        )

        outfits = (
            Outfit.objects.filter(
                weekly_plan=plan,
                date__gte=outfit_start,
                date__lte=week_end,
            )
            .prefetch_related("items__garment")
            .order_by("date")
        )

    has_plan = plan is not None and outfits.exists()

    return render(
        request,
        "planner/current.html",
        {
            "plan": plan,
            "outfits": outfits,
            "week_end": week_end,
            "selected_week": selected_week,
            "is_current_week": selected_week == "current",
            "has_plan": has_plan,
            "today": today,
            "current_week_start": current_week_start,
            "next_week_start": next_week_start,
        },
    )


@login_required
def weekly_plan(request, pk):
    delete_expired_outfits(request.user)

    plan = get_object_or_404(
        WeeklyPlan,
        pk=pk,
        user=request.user,
    )

    (
        today,
        current_week_start,
        next_week_start,
    ) = get_week_starts()

    if (
        plan.week_start not in {
            current_week_start,
            next_week_start,
        }
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

    outfit_start = (
        today
        if selected_week == "current"
        else plan.week_start
    )

    outfits = (
        Outfit.objects.filter(
            weekly_plan=plan,
            date__gte=outfit_start,
            date__lte=week_end,
        )
        .prefetch_related("items__garment")
        .order_by("date")
    )

    return render(
        request,
        "planner/weekly.html",
        {
            "plan": plan,
            "outfits": outfits,
            "week_end": week_end,
            "selected_week": selected_week,
        },
    )
