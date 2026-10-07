from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from planner.models import WeeklyPlan

from .forms import EmailAuthenticationForm, SignUpForm
from .models import Profile


def home(request):
    active_plan = None
    active_plan_end = None

    if request.user.is_authenticated:
        today = timezone.localdate()

        active_plan = (
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
            .first()
        )

        if active_plan:
            active_plan_end = (
                active_plan.week_start
                + timedelta(days=6)
            )

            if today > active_plan_end:
                active_plan = None
                active_plan_end = None

    return render(
        request,
        "home.html",
        {
            "active_plan": active_plan,
            "active_plan_end": active_plan_end,
        },
    )


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:home")

    if request.method == "POST":
        form = SignUpForm(request.POST)

        if form.is_valid():
            user = form.save()

            Profile.objects.create(
                user=user
            )

            login(request, user)

            messages.success(
                request,
                "Your account has been created."
            )

            return redirect("accounts:home")

    else:
        form = SignUpForm()

    return render(
        request,
        "accounts/signup.html",
        {"form": form}
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:home")

    if request.method == "POST":
        form = EmailAuthenticationForm(
            request,
            data=request.POST
        )

        if form.is_valid():
            login(
                request,
                form.get_user()
            )

            return redirect("accounts:home")

    else:
        form = EmailAuthenticationForm()

    return render(
        request,
        "accounts/login.html",
        {"form": form},
    )


@login_required
def logout_view(request):
    logout(request)

    return redirect(
        "accounts:home"
    )