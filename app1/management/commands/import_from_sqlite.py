import json
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from app1.models import UploadedName


class Command(BaseCommand):
    help = 'Import data from a local SQLite file into the current database (PostgreSQL)'

    def add_arguments(self, parser):
        parser.add_argument(
            'sqlite_path',
            type=str,
            help='Path to the local db.sqlite3 file'
        )
        parser.add_argument(
            '--skip-images',
            action='store_true',
            help='Skip importing large base64 images (import metadata only)'
        )

    def handle(self, *args, **options):
        sqlite_path = options['sqlite_path']
        skip_images = options['skip_images']

        if not os.path.exists(sqlite_path):
            self.stderr.write(self.style.ERROR(f'File not found: {sqlite_path}'))
            return

        import sqlite3
        src_conn = sqlite3.connect(sqlite_path)
        src_conn.row_factory = sqlite3.Row
        cursor = src_conn.cursor()

        cursor.execute('SELECT * FROM app1_uploadedname ORDER BY id')
        rows = cursor.fetchall()

        self.stdout.write(f'Found {len(rows)} records in SQLite')
        if skip_images:
            self.stdout.write(self.style.WARNING('Skipping large image data - metadata only'))

        created = 0
        skipped = 0
        updated = 0
        errors = []

        for i, row in enumerate(rows):
            try:
                existing = UploadedName.objects.filter(id=row['id']).first()
                
                # Handle large images - optionally skip or truncate
                images_json = row['images_json'] or '[]'
                img_size = len(images_json)
                
                if skip_images and img_size > 10000:  # Skip images > 10KB base64
                    images_json = '[]'  # Empty array placeholder
                    self.stdout.write(f'  [{i+1}/{len(rows)}] ID {row["id"]} - SKIPPED large images ({img_size} chars)')

                if existing:
                    existing.name = row['name']
                    existing.content = row['content'] or ''
                    existing.data_type = row['data_type'] or 'general'
                    existing.received = bool(row['received'])
                    existing.deleted = bool(row['deleted'])
                    existing.image_count = row['image_count'] or 0
                    existing.images_json = images_json
                    existing.graph_json = row['graph_json']
                    existing.image_anchors = row['image_anchors']
                    existing.save()
                    updated += 1
                else:
                    with transaction.atomic():
                        obj = UploadedName(
                            id=row['id'],
                            name=row['name'],
                            content=row['content'] or '',
                            data_type=row['data_type'] or 'general',
                            received=bool(row['received']),
                            deleted=bool(row['deleted']),
                            image_count=row['image_count'] or 0,
                            images_json = images_json,
                            graph_json=row['graph_json'],
                            image_anchors=row['image_anchors'],
                        )
                        obj.save()
                        created += 1

                if not skip_images or img_size <= 10000:
                    dtype = row['data_type'] or 'general'
                    self.stdout.write(f'  [{i+1}/{len(rows)}] ID {row["id"]} ({dtype}) - OK ({img_size} chars images)')

            except Exception as e:
                skipped += 1
                err_msg = f'  [{i+1}/{len(rows)}] ID {row["id"]} ({row["data_type"]}) FAILED: {e}'
                errors.append(err_msg)
                self.stderr.write(self.style.ERROR(err_msg))

        src_conn.close()

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! Created: {created}, Updated: {updated}, Skipped: {skipped}'
        ))
        if errors:
            self.stderr.write(self.style.WARNING(f'\n{len(errors)} errors occurred. See above for details.'))
            self.stdout.write(self.style.NOTICE('If images are too large, try: python manage.py import_from_sqlite db.sqlite3 --skip-images'))
