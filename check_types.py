from app1.models import UploadedName
from django.db.models import Count

print('Data types in database:')
for t in UploadedName.objects.filter(deleted=False).values('data_type').annotate(count=Count('id')):
    print(f"  {repr(t['data_type'])}: {t['count']}")

print()
print(f"NULL data_type: {UploadedName.objects.filter(data_type__isnull=True, deleted=False).count()}")
print(f"Empty data_type: {UploadedName.objects.filter(data_type='', deleted=False).count()}")
