# ADMINPANEL\server\server\urls.py
from django.contrib import admin
from django.urls import path, include
from app1 import views as app1_views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("app1/", include("app1.urls")),
    # Root goes to smart login, which then routes:
    # superuser → full admin, others → staff-only panel
    path("", app1_views.login_view, name="root-login"),
]