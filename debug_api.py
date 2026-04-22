from app1.models import UploadedName

items = UploadedName.objects.filter(deleted=False).order_by('-id')
print(f'Total from DB: {items.count()}')

data_list = []
for item in items:
    record = {
        'id': item.id,
        'name': item.name,
        'type': item.data_type,
        'received': item.received,
    }
    data_list.append(record)

print(f'JSON items: {len(data_list)}')
counts = {}
for d in data_list:
    t = d['type'] or 'None'
    counts[t] = counts.get(t, 0) + 1
print('By type:', counts)
print()
print('First 10 items:')
for d in data_list[:10]:
    print(f"  ID {d['id']}: type={repr(d['type'])}, name={d['name'][:25]}")
