import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = 'Block until the default database accepts connections (works with DATABASE_URL or DB_* vars).'

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=90)

    def handle(self, *args, **options):
        deadline = time.monotonic() + options['timeout']
        while True:
            try:
                connections['default'].ensure_connection()
                self.stdout.write(self.style.SUCCESS('Database is available'))
                return
            except OperationalError as exc:
                if time.monotonic() > deadline:
                    raise CommandError(f'Database not available after {options["timeout"]}s: {exc}')
                self.stdout.write('Waiting for database...')
                time.sleep(2)
