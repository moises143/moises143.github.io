# ADMINPANEL\server\app1\urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),  
    path("upload/", views.upload_name, name="upload"),
    path("check-new/<str:last_sync>/", views.check_new, name="check_new"),
    path("mark-received/", views.mark_received, name="mark_received"),
    path("graph/latest/", views.latest_graph, name="latest_graph"),
    path("delete/", views.delete_data, name="delete"),
    path("delete-building/", views.delete_building, name="delete_building"),
    path("get-all/", views.get_all_data, name="get_all"),
    path("admin-page/", views.admin_page, name="admin-page"),
    path(
        "distributed-admins/new/",
        views.create_distributed_admin,
        name="create-distributed-admin",
    ),
    path("staff-admin/", views.staff_admin_page, name="staff-admin"),
    path("test/", views.test_api, name="test-api"),
]