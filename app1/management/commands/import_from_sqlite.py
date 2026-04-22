import json
import os
from django.core.management.base import BaseCommand
from django.db import connection
from app1.models import UploadedName


class Command(BaseCommand):
    help = 'Import data from a local SQLite file into the current database (PostgreSQL)'

    def add_arguments(self, parser):
        parser.add_argument(
            'sqlite_path',
            type=str,
            help='Path to the local db.sqlite3 file'
        )

    def handle(self, *args, **options):
        sqlite_path = options['sqlite_path']

        if not os.path.exists(sqlite_path):
            self.stderr.write(self.style.ERROR(f'File not found: {sqlite_path}'))
            return

        # Connect to the SQLite file directly
        import sqlite3
        src_conn = sqlite3.connect(sqlite_path)
        src_conn.row_factory = sqlite3.Row
        cursor = src_conn.cursor()

        # Get all records
        cursor.execute('SELECT * FROM app1_uploadedname ORDER BY id')
        rows = cursor.fetchall()

        self.stdout.write(f'Found {len(rows)} records in SQLite')

        created = 0
        skipped = 0
        updated = 0

        for row in rows:
            # Check if record already exists in target DB
            existing = UploadedName.objects.filter(id=row['id']).first()

            if existing:
                # Update existing record
                existing.name = row['name']
                existing.content = row['content'] or ''
                existing.data_type = row['data_type'] or 'general'
                existing.received = bool(row['received'])
                existing.deleted = bool(row['deleted'])
                existing.image_count = row['image_count'] or 0
                existing.images_json = row['images_json'] or '[]'
                existing.graph_json = row['graph_json']
                existing.image_anchors = row['image_anchors']
                existing.save()
                updated += 1
            else:
                # Create new record with specific ID
                obj = UploadedName(
                    id=row['id'],
                    name=row['name'],
                    content=row['content'] or '',
                    data_type=row['data_type'] or 'general',
                    received=bool(row['received']),
                    deleted=bool(row['deleted']),
                    image_count=row['image_count'] or 0,
                    images_json=row['images_json'] or '[]',
                    graph_json=row['graph_json'],
                    image_anchors=row['image_anchors'],
                )
                obj.save()
                created += 1

            if (created + updated) % 50 == 0:
                self.stdout.write(f'  Processed {created + updated}/{len(rows)}...')

        src_conn.close()

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! Created: {created}, Updated: {updated}, Skipped: {skipped}'
        ))
