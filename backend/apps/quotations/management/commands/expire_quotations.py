from django.core.management.base import BaseCommand

from apps.quotations.services import expire_due_quotations


class Command(BaseCommand):
    help = "Mark sent quotations whose valid-until date has passed as Expired (run daily)."

    def handle(self, *args, **options):
        n = expire_due_quotations()
        self.stdout.write(self.style.SUCCESS(f"{n} quotation(s) expired."))
