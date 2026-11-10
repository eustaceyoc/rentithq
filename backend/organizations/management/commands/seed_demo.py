from django.core.management.base import BaseCommand

from organizations.demo_seed import seed_demo


class Command(BaseCommand):
    help = (
        "Create a DEMO workspace with sample properties and residents. "
        "Safe to run again. DEMO_EMAIL and DEMO_PASSWORD come from the environment."
    )

    def handle(self, *args: object, **options: object) -> None:
        self.stdout.write(seed_demo())
