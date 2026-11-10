from argparse import ArgumentParser
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from billing.recurrence import workspace_today
from notifications.services import send_reminders
from organizations.models import Workspace


class Command(BaseCommand):
    help = (
        "Email due-soon and overdue notices for one workspace. "
        "The same invoice is not emailed twice for the same kind of notice."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--as-of", dest="as_of", default="")
        parser.add_argument("--workspace", dest="workspace", default="")

    def handle(self, *args: object, **options: object) -> None:
        raw_as_of = str(options.get("as_of") or "")
        workspace_id = str(options.get("workspace") or "")
        queryset = Workspace.objects.filter(status=Workspace.Status.ACTIVE)
        if workspace_id:
            queryset = queryset.filter(id=workspace_id)
        if not queryset.exists():
            raise CommandError("No workspace matched.")
        for workspace in queryset:
            as_of = (
                date.fromisoformat(raw_as_of)
                if raw_as_of
                else workspace_today(workspace)
            )
            run = send_reminders(workspace, as_of)
            self.stdout.write(f"{workspace.id} sent={run.created_count}")
