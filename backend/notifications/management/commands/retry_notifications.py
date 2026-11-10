from django.core.management.base import BaseCommand

from notifications.services import retry_failed


class Command(BaseCommand):
    help = "Retry failed notification deliveries, at most three attempts each."

    def handle(self, *args: object, **options: object) -> None:
        sent = retry_failed()
        self.stdout.write(f"sent {sent}")
