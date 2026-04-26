"""
sync_translations — Django management command

Reads a translations.json file produced by the frontend
extract-translations.mjs script and upserts Translation rows
for the English language.

Only English (the source language) is written.
Other languages are left untouched — they are managed separately
via the admin or fixtures.

Usage:
    python manage.py sync_translations
    python manage.py sync_translations --file /path/to/translations.json
    python manage.py sync_translations --dry-run
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from localization.models import Language, Translation

# Default path: repo-root/translations.json  (one level above microdrama-site/)
DEFAULT_FILE = Path(__file__).resolve().parents[6] / "translations.json"


class Command(BaseCommand):
    help = "Sync translation keys from the frontend translations.json into the DB (English only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(DEFAULT_FILE),
            help="Path to translations.json (default: %(default)s)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without writing to the DB.",
        )
        parser.add_argument(
            "--prune",
            action="store_true",
            help=(
                "Delete English Translation rows whose keys are no longer "
                "present in the JSON file. Use with caution."
            ),
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        dry_run = options["dry_run"]
        prune = options["prune"]

        # ------------------------------------------------------------------ #
        # Load JSON
        # ------------------------------------------------------------------ #
        if not file_path.exists():
            raise CommandError(
                f"translations.json not found at {file_path}\n"
                "Run `npm run extract-translations` in movbits-app first."
            )

        try:
            incoming: dict[str, str] = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {file_path}: {exc}") from exc

        if not isinstance(incoming, dict):
            raise CommandError(
                "translations.json must be a JSON object at the top level."
            )

        self.stdout.write(f"Loaded {len(incoming)} keys from {file_path}")

        # ------------------------------------------------------------------ #
        # Resolve English language row
        # ------------------------------------------------------------------ #
        try:
            english = Language.objects.get(code="en")
        except Language.DoesNotExist:
            raise CommandError(
                'No Language row with code="en" found. '
                "Run `python manage.py loaddata localization/fixtures/languages.json` first."
            )

        # ------------------------------------------------------------------ #
        # Upsert
        # ------------------------------------------------------------------ #
        existing = {t.key: t for t in Translation.objects.filter(language=english)}

        created = []
        updated = []
        skipped = []

        for key, default_value in incoming.items():
            if key in existing:
                row = existing[key]
                if row.value != default_value and default_value != "":
                    if not dry_run:
                        row.value = default_value
                        row.save(update_fields=["value"])
                    updated.append((key, default_value))
                else:
                    skipped.append(key)
            else:
                if not dry_run:
                    Translation.objects.create(
                        language=english,
                        key=key,
                        value=default_value,
                    )
                created.append((key, default_value))

        # ------------------------------------------------------------------ #
        # Prune
        # ------------------------------------------------------------------ #
        pruned = []
        if prune:
            incoming_keys = set(incoming.keys())
            for key, row in existing.items():
                if key not in incoming_keys:
                    pruned.append(key)
                    if not dry_run:
                        row.delete()

        # ------------------------------------------------------------------ #
        # Report
        # ------------------------------------------------------------------ #
        prefix = "[DRY RUN] " if dry_run else ""

        if created:
            self.stdout.write(
                self.style.SUCCESS(f"{prefix}Created {len(created)} keys:")
            )
            for key, value in created:
                self.stdout.write(f"  + {key!r}  →  {value!r}")

        if updated:
            self.stdout.write(
                self.style.WARNING(f"{prefix}Updated {len(updated)} keys:")
            )
            for key, value in updated:
                self.stdout.write(f"  ~ {key!r}  →  {value!r}")

        if pruned:
            self.stdout.write(self.style.ERROR(f"{prefix}Pruned {len(pruned)} keys:"))
            for key in pruned:
                self.stdout.write(f"  - {key!r}")

        self.stdout.write(
            f"\n{prefix}Done — "
            f"{len(created)} created, {len(updated)} updated, "
            f"{len(skipped)} unchanged, {len(pruned)} pruned."
        )
