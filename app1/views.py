# ADMINPANEL\server\app1\views.py
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import UploadedName
import json
import base64
import logging
import re
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

# ============= ANDROID APP API ENDPOINTS =============

@csrf_exempt
@require_http_methods(["GET"])
def check_new(request, last_sync):
    """
    Android app calls this with last_sync as integer ID (legacy) or timestamp (ISO format) or '0' for full sync.
    Returns all items with id > last_sync (if integer) or last_modified > last_sync (if timestamp).
    """
    try:
        logger.info(f"📱 Android check_new request - Last sync: {last_sync}")
        
        if last_sync == '0':
            # Full sync: return all non-deleted items
            items = UploadedName.objects.filter(deleted=False).order_by('id')
            logger.info(f"📊 Fresh install - returning ALL {items.count()} items")
        else:
            # Try to parse as integer ID first (Android legacy mode)
            if last_sync.isdigit():
                last_id = int(last_sync)
                items = UploadedName.objects.filter(id__gt=last_id, deleted=False).order_by('id')
                logger.info(f"📊 Incremental by ID: items with id > {last_id} → {items.count()} items")
            else:
                # Normal timestamp mode
                from django.utils.dateparse import parse_datetime
                last_sync_dt = parse_datetime(last_sync)
                if last_sync_dt is None:
                    return JsonResponse({"error": "Invalid timestamp"}, status=400)
                items = UploadedName.objects.filter(last_modified__gt=last_sync_dt).order_by('id')
                logger.info(f"📊 Incremental by timestamp: items after {last_sync} → {items.count()} items")
        
        data = []
        for item in items:
            timestamp = item.timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            
            # Base response with ALL fields Android needs
            response_item = {
                "id": item.id,
                "name": item.name,
                "timestamp": timestamp,
                "type": item.data_type if item.data_type else 'general',
                "received": item.received,
                "deleted": item.deleted,
                "last_modified": item.last_modified.isoformat()
            }
            
            # ===== STAFF DATA =====
            if item.data_type == 'staff':
                content_lines = item.content.strip().split('\n') if item.content else []
                cleaned_lines = []
                for line in content_lines:
                    cleaned = line.strip().replace('"', '')
                    if cleaned:
                        cleaned_lines.append(cleaned)

                # Expected format:
                # [0] staff_key, [1] full_name, [2] badge, [3] "ABOUT", [4] full_position, [5] location, [6+] extra
                if len(cleaned_lines) >= 6:
                    response_item["staff_name"] = cleaned_lines[0]      # staff key (e.g., "staff_john_doe")
                    response_item["full_name"] = cleaned_lines[1]       # e.g., "John Doe"
                    response_item["badge"] = cleaned_lines[2]           # e.g., "Professor"
                    response_item["position"] = cleaned_lines[4]        # FULL position (e.g., "Master of Science in IT")
                    response_item["location"] = cleaned_lines[5]        # e.g., "IT Building"
                    if len(cleaned_lines) > 6:
                        response_item["additional"] = "\n".join(cleaned_lines[6:])
                else:
                    logger.error(f"Staff data for ID {item.id} has insufficient lines: {cleaned_lines}")

                # Staff image (unchanged)
                images = item.get_images()
                if images and len(images) > 0:
                    response_item["imageData"] = images[0].get("data", "")
                    response_item["imageFilename"] = images[0].get("filename", f"{cleaned_lines[0]}_profile.jpg")
                    logger.info(f"📸 Adding staff image for {cleaned_lines[1] if len(cleaned_lines)>1 else 'unknown'}")
            
            # ===== CAMPUS DATA (GRAPH-BASED) =====
            elif item.data_type == 'campus':
                # Include graph JSON if available
                if item.graph_json:
                    try:
                        response_item["graph"] = json.loads(item.graph_json)
                        logger.info(f"📊 Sending graph with {len(response_item['graph'].get('nodes',[]))} nodes")
                    except:
                        response_item["graph"] = None
                else:
                    response_item["graph"] = None
                
                # Include image anchors if available
                if item.image_anchors:
                    try:
                        response_item["image_anchors"] = json.loads(item.image_anchors)
                    except:
                        response_item["image_anchors"] = {}
                else:
                    response_item["image_anchors"] = {}
                
                # Parse legacy content for backward compatibility
                content_lines = item.content.strip().split('\n') if item.content else []
                
                map_name = ""
                latitude = ""
                longitude = ""
                destination_name = ""
                image_count = 0
                
                for line in content_lines:
                    line = line.strip().replace('"', '')
                    if line.startswith('map '):
                        map_name = line
                        response_item["map_name"] = line
                    elif line.startswith('lat:'):
                        latitude = line.replace('lat:', '')
                        response_item["latitude"] = latitude
                    elif line.startswith('long:'):
                        longitude = line.replace('long:', '')
                        response_item["longitude"] = longitude
                    elif line.startswith('destination_name:'):
                        destination_name = line.replace('destination_name:', '')
                        response_item["destination_name"] = destination_name
                    elif line.startswith('image_count:'):
                        try:
                            image_count = int(line.replace('image_count:', ''))
                            response_item["image_count"] = image_count
                        except:
                            response_item["image_count"] = 0
                
                # Get campus images from images_json
                images = item.get_images()
                if images and len(images) > 0:
                    campus_images = []
                    for img in images:
                        campus_images.append({
                            "filename": img.get("filename", ""),
                            "originalName": img.get("originalName", ""),
                            "data": img.get("data", ""),
                            "type": img.get("type", "image/jpeg")
                        })
                    response_item["images"] = campus_images
                    response_item["image_count"] = len(campus_images)
                    logger.info(f"📸 Adding {len(campus_images)} campus images for {destination_name}")
                    
            # ===== GRAPH DATA =====
            elif item.data_type == 'graph':
                # Send graph JSON as is
                if item.graph_json:
                    try:
                        response_item["graph"] = json.loads(item.graph_json)
                        logger.info(f"📊 Sending graph (ID {item.id}) with {len(response_item['graph'].get('nodes',[]))} nodes")
                    except Exception as e:
                        logger.error(f"Failed to parse graph JSON: {e}")
                        response_item["graph"] = None
                else:
                    response_item["graph"] = None
                # No need to parse content or images
            
            data.append(response_item)
            
        
        logger.info(f"📱 Returning {len(data)} items to Android")
        return JsonResponse(data, safe=False)
        
    except Exception as e:
        logger.error(f"🔥 Error in check_new: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse([], safe=False)


@csrf_exempt
@require_http_methods(["POST"])
def mark_received(request):
    """Android marks item as received"""
    try:
        body = json.loads(request.body.decode('utf-8'))
        item_id = body.get("id")
        
        if not item_id:
            return JsonResponse({"error": "Missing ID"}, status=400)
        
        updated = UploadedName.objects.filter(id=item_id).update(received=True)
        
        if updated:
            logger.info(f"📱 Android marked ID {item_id} as received ✓")
            return JsonResponse({"status": "ok"})
        else:
            return JsonResponse({"error": "Item not found"}, status=404)
            
    except Exception as e:
        logger.error(f"🔥 Error in mark_received: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def latest_graph(request):
    """
    Return the most recent graph record (by timestamp).
    Android calls this to fetch the latest graph without needing IDs.
    """
    try:
        graph_item = UploadedName.objects.filter(data_type='graph').order_by('-timestamp').first()
        if not graph_item:
            return JsonResponse({"exists": False})

        return JsonResponse({
            "exists": True,
            "id": graph_item.id,
            "timestamp": graph_item.timestamp.isoformat(),
            "graph_json": json.loads(graph_item.graph_json) if graph_item.graph_json else None
        })
    except Exception as e:
        logger.error(f"Error in latest_graph: {e}")
        return JsonResponse({"error": str(e)}, status=500)


# ============= AUTH & ADMIN PANEL ENDPOINTS =============

def login_view(request):
    """
    Smart login that routes users based on their role:
    - Superuser → full admin panel
    - Non-superuser authenticated user → distributed admin (staff-only)
    """
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect("admin-page")
        return redirect("staff-admin")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(request, username=username, password=password)
        if user is None:
            return render(
                request,
                "login.html",
                {"error": "Invalid username or password.", "username": username},
            )

        login(request, user)
        if user.is_superuser:
            return redirect("admin-page")
        return redirect("staff-admin")

    return render(request, "login.html")


@login_required
def logout_view(request):
    """Log out the current user and redirect to login page."""
    logout(request)
    return redirect("login")


@login_required
def admin_page(request):
    """Render the full admin panel (superusers)."""
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only superadmins can view this page.")
    return render(request, "admin.html")


@login_required
def staff_admin_page(request):
    """
    Render the distributed admin panel – staff adding only.
    Non‑superuser staff accounts only.
    """
    if request.user.is_superuser:
        return redirect("admin-page")
    if not request.user.is_staff:
        return HttpResponseForbidden("Only distributed admins can view this page.")

    # Fetch all campus names for autocomplete suggestions
    campuses = UploadedName.objects.filter(data_type='campus').values_list('name', flat=True)
    campus_list = list(campuses)

    return render(request, "staff_admin.html", {
        "campus_list": json.dumps(campus_list)
    })


@login_required
def create_distributed_admin(request):
    """
    Superadmin-only view to create distributed admin accounts
    (non-superuser staff users).
    """
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only superadmins can create distributed admins.")

    context = {}

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password1 = request.POST.get("password1", "")
        password2 = request.POST.get("password2", "")
        email = request.POST.get("email", "").strip()

        errors = []
        if not username:
            errors.append("Username is required.")
        if User.objects.filter(username=username).exists():
            errors.append("That username is already taken.")
        if not password1 or not password2:
            errors.append("Password is required.")
        elif password1 != password2:
            errors.append("Passwords do not match.")
        elif len(password1) < 6:
            errors.append("Password must be at least 6 characters long.")

        if errors:
            context["errors"] = errors
            context["username"] = username
            context["email"] = email
        else:
            user = User.objects.create_user(
                username=username,
                email=email or "",
                password=password1,
            )
            # Mark as staff but not superuser → distributed admin
            user.is_staff = True
            user.is_superuser = False
            user.save()
            context["success"] = f"Distributed admin account '{username}' created."

    return render(request, "create_distributed_admin.html", context)


@csrf_exempt
@require_http_methods(["POST"])
def upload_name(request):
    """
    Admin panel uploads new data with images.
    If 'id' is provided, updates the existing record; otherwise creates a new one.
    Handles graph_json and image_anchors for graph-based campuses.
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
        content = data.get("content", "")
        data_type = data.get("type", "general")
        images = data.get("images", [])
        item_id = data.get("id")  # may be None for new items
        
        # NEW: Flag to keep existing images when editing
        keep_existing = data.get("keepExistingImages", False)
        
        # Graph builder fields
        graph_json = data.get("graph_json")
        image_anchors = data.get("image_anchors")

        logger.info(f"📝 Admin upload - Type: {data_type}, Images: {len(images)}, ID: {item_id}, KeepExisting: {keep_existing}")

        if not content or not content.strip():
            return JsonResponse({"error": "Empty content"}, status=400)

        # Extract name from first line
        first_line = content.strip().split('\n')[0]
        name = first_line.replace('"', '').strip()
        if len(name) > 255:
            name = name[:252] + "..."

        # Process new images from the request
        new_image_data = []
        for img in images:
            if img.get("dataUrl", "").startswith('data:image'):
                new_image_data.append({
                    "filename": img.get("autoName", f"image_{len(new_image_data)}.jpg"),
                    "originalName": img.get("originalName", "unknown.jpg"),
                    "data": img.get("dataUrl", ""),
                    "type": img.get("type", "image/jpeg")
                })

        if item_id:
            # Update existing record
            try:
                obj = UploadedName.objects.get(id=item_id)
                
                # Get existing images if we need to keep them
                existing_images = []
                if keep_existing:
                    existing_images = obj.get_images()
                    logger.info(f"📸 Keeping {len(existing_images)} existing images")
                
                obj.name = name
                obj.content = content
                obj.data_type = data_type
                obj.received = False  # reset so app syncs again
                
                # Save graph fields if provided
                if graph_json is not None:
                    obj.graph_json = json.dumps(graph_json) if isinstance(graph_json, dict) else graph_json
                if image_anchors is not None:
                    obj.image_anchors = json.dumps(image_anchors) if isinstance(image_anchors, dict) else image_anchors
                
                # Save the object first (without images)
                obj.save()
                logger.info(f"✅ Updated item ID {item_id}")
                
                # Send WebSocket notification for all data types
                if obj.id:
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        'sync_group',
                        {
                            'type': 'send_update',
                            'update_type': 'data_updated',
                            'data_type': data_type,
                            'message': f'{data_type} has been updated'
                        }
                    )
                    logger.info(f"📡 WebSocket notification sent for {data_type} ID {obj.id}")
                
                # Merge existing and new images
                if keep_existing:
                    all_images = existing_images + new_image_data
                    
                    # Parse the content to get the expected image count (legacy)
                    content_lines = content.strip().split('\n')
                    expected_count = 0
                    for line in content_lines:
                        if line.startswith('"image_count:'):
                            try:
                                count_str = line.replace('"', '').replace('image_count:', '').strip()
                                expected_count = int(count_str)
                                break
                            except:
                                pass
                    
                    # If we have an expected count from content, use it to trim images
                    if expected_count > 0:
                        all_images = all_images[:expected_count]
                        logger.info(f"📊 Trimming to {expected_count} images based on content")
                    
                    obj.set_images(all_images)
                else:
                    if new_image_data:
                        obj.set_images(new_image_data)
                    else:
                        obj.set_images([])
                
                obj.save()
                
            except UploadedName.DoesNotExist:
                return JsonResponse({"error": "Item not found"}, status=404)
        else:
            # Create new record
            obj = UploadedName.objects.create(
                name=name,
                content=content,
                data_type=data_type,
                received=False
            )
            # Save graph fields if provided
            if graph_json is not None:
                obj.graph_json = json.dumps(graph_json) if isinstance(graph_json, dict) else graph_json
            if image_anchors is not None:
                obj.image_anchors = json.dumps(image_anchors) if isinstance(image_anchors, dict) else image_anchors
            
            logger.info(f"✅ Created new item ID {obj.id}")
            
            # Send WebSocket notification for all data types
            if obj.id:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    'sync_group',
                    {
                        'type': 'send_update',
                        'update_type': 'data_updated',
                        'data_type': data_type,
                        'message': f'{data_type} has been updated'
                    }
                )
                logger.info(f"📡 WebSocket notification sent for {data_type} ID {obj.id}")
            
            # Save images for new record
            if new_image_data:
                obj.set_images(new_image_data)
                obj.save()

        return JsonResponse({
            "status": "success",
            "id": obj.id,
            "image_count": obj.image_count if obj.image_count else 0,
            "message": "Data and images saved successfully"
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"🔥 Error in upload_name: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)


def get_all_data(request):
    """Get all records for admin panel - exclude soft-deleted items"""
    try:
        items = UploadedName.objects.filter(deleted=False).order_by('-id')
        logger.info(f"get_all_data: Found {items.count()} records in DB")
        
        data_list = []
        type_counts = {}
        
        for item in items:
            record = {
                "id": item.id,
                "name": item.name,
                "content": item.content,
                "type": item.data_type,
                "timestamp": item.timestamp.isoformat(),
                "received": item.received,
                "image_count": item.image_count if item.image_count else 0,
                # Exclude graph_json to prevent response truncation
                # graph_json is too large and not needed for list view
                "image_anchors": item.image_anchors,
            }
            
            # Add image previews
            if item.image_count and item.image_count > 0:
                try:
                    images = item.get_images()
                    record["image_previews"] = [
                        {
                            "filename": img["filename"],
                            "originalName": img["originalName"],
                        }
                        for img in images[:3]
                    ]
                except Exception as img_err:
                    logger.warning(f"Error loading images for ID {item.id}: {img_err}")
                    record["image_previews"] = []
            
            data_list.append(record)
            t = item.data_type or 'none'
            type_counts[t] = type_counts.get(t, 0) + 1
        
        logger.info(f"get_all_data: Returning {len(data_list)} records. Types: {type_counts}")
        
        response = JsonResponse({"data": data_list})
        # Prevent caching
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
        
    except Exception as e:
        logger.error(f"Error in get_all_data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_data(request):
    """
    Soft delete a record – requires superadmin password confirmation.
    Sets deleted=True and received=False so the app receives a tombstone.
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
        item_id = data.get("id")
        password = data.get("password", "")

        if not item_id:
            return JsonResponse({"error": "Missing ID"}, status=400)

        # Verify the current user's password (only superusers can delete)
        if not request.user.is_authenticated or not request.user.is_superuser:
            return JsonResponse({"error": "Unauthorized"}, status=403)

        user = authenticate(username=request.user.username, password=password)
        if user is None:
            return JsonResponse({"error": "Invalid password"}, status=403)

        # Soft delete: mark as deleted and reset received flag
        try:
            obj = UploadedName.objects.get(id=item_id)
            obj.deleted = True
            obj.received = False   # so it will be sent again as a tombstone
            obj.save()
            
            # Send WebSocket notification
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'sync_group',
                {
                    'type': 'send_update',
                    'update_type': 'data_updated',
                    'data_type': obj.data_type,
                    'message': f'{obj.data_type} has been deleted'
                }
            )
            logger.info(f"🗑️ Soft-deleted item ID {item_id} by {request.user.username} (WebSocket notified)")
        except UploadedName.DoesNotExist:
            return JsonResponse({"error": "Item not found"}, status=404)

        return JsonResponse({"status": "deleted"})

    except Exception as e:
        logger.error(f"Error in delete_data: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_building(request):
    """
    Soft delete a building – no password required.
    Sets deleted=True and received=False so the app receives a tombstone.
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
        item_id = data.get("id")

        if not item_id:
            return JsonResponse({"error": "Missing ID"}, status=400)

        # Only require authentication, no password
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=403)

        # Soft delete: mark as deleted and reset received flag
        try:
            obj = UploadedName.objects.get(id=item_id)
            obj.deleted = True
            obj.received = False   # so it will be sent again as a tombstone
            obj.save()
            
            # Send WebSocket notification
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'sync_group',
                {
                    'type': 'send_update',
                    'update_type': 'data_updated',
                    'data_type': obj.data_type,
                    'message': f'{obj.data_type} has been deleted'
                }
            )
            logger.info(f"🗑️ Building ID {item_id} soft-deleted by {request.user.username} (WebSocket notified)")
        except UploadedName.DoesNotExist:
            return JsonResponse({"error": "Item not found"}, status=404)

        return JsonResponse({"status": "deleted"})

    except Exception as e:
        logger.error(f"Error in delete_building: {e}")
        return JsonResponse({"error": str(e)}, status=500)


def test_api(request):
    """Health check endpoint"""
    total_items = UploadedName.objects.count()
    pending_items = UploadedName.objects.filter(received=False).count()
    
    # Count images
    total_images = 0
    for item in UploadedName.objects.all():
        total_images += item.image_count if item.image_count else 0
    
    return JsonResponse({
        "status": "Django server is running",
        "android_endpoints": {
            "check_new": "/app1/check-new/<last_id>/",
            "mark_received": "/app1/mark-received/",
        },
        "admin_endpoints": {
            "upload": "/app1/upload/",
            "get_all": "/app1/get-all/",
            "delete": "/app1/delete/",
            "admin": "/app1/admin/"
        },
        "stats": {
            "total_items": total_items,
            "pending_sync": pending_items,
            "synced": total_items - pending_items,
            "total_images": total_images
        }
    })