# ADMINPANEL\server\app1\models.py
from django.db import models
from django.utils import timezone

class UploadedName(models.Model):
    DATA_TYPES = [
        ('staff', 'Staff Member'),
        ('campus', 'Campus Location'),
        ('general', 'General'),
    ]
    
    name = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    received = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)
    
    # Legacy fields (kept for backward compatibility)
    content = models.TextField(blank=True, null=True, default='')
    data_type = models.CharField(max_length=20, choices=DATA_TYPES, default='general', blank=True, null=True)
    image_count = models.IntegerField(default=0, blank=True, null=True)
    images_json = models.TextField(default='[]', blank=True, null=True)
    
    # ===== NEW FIELDS FOR GRAPH‑BASED CAMPUSES =====
    graph_json = models.TextField(
        blank=True, 
        null=True,
        help_text="JSON exported from Graph Builder app (nodes + edges)."
    )
    image_anchors = models.TextField(
        blank=True,
        null=True,
        help_text="JSON mapping: {image_index: node_id, ...} indicating where each image should be anchored."
    )
    
    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return self.name
    
    def set_images(self, images):
        """Store images as JSON (legacy method)."""
        import json
        self.images_json = json.dumps(images)
        self.image_count = len(images)
    
    def get_images(self):
        """Retrieve images from JSON (legacy method)."""
        try:
            import json
            if self.images_json:
                return json.loads(self.images_json)
            return []
        except:
            return []
    
    def set_graph(self, graph_dict):
        """Store graph JSON and optionally validate it."""
        import json
        self.graph_json = json.dumps(graph_dict)
    
    def get_graph(self):
        """Retrieve graph as Python dict."""
        try:
            import json
            if self.graph_json:
                return json.loads(self.graph_json)
            return None
        except:
            return None
    
    def set_image_anchors(self, anchors_dict):
        """Store mapping of image index -> node ID."""
        import json
        self.image_anchors = json.dumps(anchors_dict)
    
    def get_image_anchors(self):
        """Retrieve image anchors dict."""
        try:
            import json
            if self.image_anchors:
                return json.loads(self.image_anchors)
            return {}
        except:
            return {}