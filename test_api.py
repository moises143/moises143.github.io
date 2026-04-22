from app1.models import UploadedName
import json

def test_get_all():
    items = UploadedName.objects.filter(deleted=False).order_by('-id')
    print(f"DB count: {items.count()}")
    
    data_list = []
    errors = []
    
    for i, item in enumerate(items):
        try:
            record = {
                "id": item.id,
                "name": item.name,
                "content": item.content,
                "type": item.data_type,
                "timestamp": item.timestamp.isoformat(),
                "received": item.received,
                "image_count": item.image_count if item.image_count else 0,
                "graph_json": item.graph_json,
                "image_anchors": item.image_anchors,
            }
            
            # This is where the API might fail
            if item.image_count and item.image_count > 0:
                try:
                    images = item.get_images()
                    record["image_previews"] = [
                        {"filename": img["filename"], "originalName": img["originalName"]}
                        for img in images[:3]
                    ]
                except Exception as e:
                    errors.append(f"ID {item.id} image error: {e}")
                    record["image_previews"] = []
            
            data_list.append(record)
            
        except Exception as e:
            errors.append(f"ID {item.id} FAILED: {e}")
    
    print(f"Successfully processed: {len(data_list)}")
    print(f"Errors: {len(errors)}")
    if errors:
        for e in errors[:5]:
            print(f"  {e}")
    
    # Count by type
    counts = {}
    for d in data_list:
        t = d['type'] or 'None'
        counts[t] = counts.get(t, 0) + 1
    print(f"By type: {counts}")

test_get_all()
