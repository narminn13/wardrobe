from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

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
def current_week(request):
    today = timezone.localdate()

    plans = (
        WeeklyPlan.objects
        .filter(
            user=request.user,
            status=WeeklyPlan.STATUS_GENERATED,
            week_start__lte=today,
        )
        .prefetch_related(
            "outfits__items__garment"
        )
        .order_by("-week_start")
    )

    active_plan = None

    for plan in plans:
        week_end = plan.week_start + timedelta(days=6)

        if plan.week_start <= today <= week_end:
            active_plan = plan
            break

    if active_plan is None:
        messages.info(
            request,
            "You don't have a current weekly outfit plan yet.",
        )

        return redirect(
            "planner:create"
        )

    week_end = (
        active_plan.week_start
        + timedelta(days=6)
    )

    return render(
        request,
        "planner/current.html",
        {
            "plan": active_plan,
            "week_end": week_end,
        },
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

    today = timezone.localdate()

    week_end = (
        plan.week_start
        + timedelta(days=6)
    )

    if (
        today < plan.week_start
        or today > week_end
        or plan.status != WeeklyPlan.STATUS_GENERATED
    ):
        messages.info(
            request,
            "This weekly outfit plan is no longer active.",
        )

        return redirect(
            "accounts:home"
        )

    return render(
        request,
        "planner/weekly.html",
        {
            "plan": plan,
            "week_end": week_end,
        },
    )