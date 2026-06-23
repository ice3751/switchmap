from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from inventory import dashboard_views, ssh_views
from inventory.access_control import refresh_required, operator_or_admin_required


urlpatterns = [
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path(
        "refresh-all/",
        refresh_required(dashboard_views.switchmap_refresh_all_data),
        name="switchmap_refresh_all_data",
    ),
    path("admin/", admin.site.urls),
    path(
        "ssh-action/",
        operator_or_admin_required(ssh_views.port_ssh_action),
        name="global_port_ssh_action",
    ),
    path(
        "switch/<int:switch_id>/ssh-action/",
        operator_or_admin_required(ssh_views.port_ssh_action),
        name="global_switch_port_ssh_action",
    ),
    path("", include("inventory.urls")),
]
