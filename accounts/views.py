from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import EmailAuthenticationForm, SignUpForm
from .models import Profile


def home(request):
    return render(request, "home.html")


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
        {"form": form}
    )


@login_required
def logout_view(request):
    logout(request)
    return redirect("accounts:home")