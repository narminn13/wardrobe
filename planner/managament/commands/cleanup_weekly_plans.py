from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from planner.models import WeeklyPlan


class Command(BaseCommand):
    help = "Delete weekly plans that have already ended."

    def handle(self, *args, **options):
        today = timezone.localdate()

        cutoff_date = today - timedelta(days=6)

        expired_plans = WeeklyPlan.objects.filter(
            week_start__lt=cutoff_date
        )

        count = expired_plans.count()

        expired_plans.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {count} expired weekly plan(s)."
            )
        )