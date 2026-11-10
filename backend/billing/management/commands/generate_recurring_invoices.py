from argparse import ArgumentParser
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from billing.recurrence import generate_for_workspace, workspace_today
from organizations.models import Workspace


class Command(BaseCommand):
    help = (
        "Issue rent invoices for agreement periods due on or before a date. "
        "Safe to run again. Nothing is scheduled until cron calls this command."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--as-of", dest="as_of", default="")
        parser.add_argument("--workspace", dest="workspace", default="")
        parser.add_argument("--dry-run", action="store_true", dest="dry_run")

    def handle(self, *args: object, **options: object) -> None:
        raw_as_of = str(options.get("as_of") or "")
        workspace_id = str(options.get("workspace") or "")
        dry_run = bool(options.get("dry_run"))
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
            run = generate_for_workspace(workspace, as_of, dry_run=dry_run)
            self.stdout.write(
                f"{workspace.id} created={run.created_count} "
                f"skipped={run.skipped_count} status={run.status}"
            )
