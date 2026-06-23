import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.test import Client, override_settings
from django.urls import reverse

django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from inventory.access_control import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEW_ONLY, user_role
from inventory.models import SystemAuditLog

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "127.0.0.1", "localhost"], DEBUG=True)
def main():
    for role in (ROLE_VIEW_ONLY, ROLE_OPERATOR, ROLE_ADMIN):
        Group.objects.get_or_create(name=role)

    User.objects.filter(username__in=[
        "switchmap_phase32_admin",
        "switchmap_phase32_viewer",
        "switchmap_phase32_user",
    ]).delete()

    admin = User.objects.create_superuser(
        username="switchmap_phase32_admin",
        email="phase32-admin@example.local",
        password="Phase32AdminPass!",
    )
    viewer = User.objects.create_user(
        username="switchmap_phase32_viewer",
        password="Phase32ViewerPass!",
    )
    viewer.groups.add(Group.objects.get(name=ROLE_VIEW_ONLY))

    client = Client()
    client.force_login(admin)

    response = client.get(reverse("inventory:user_management"))
    assert response.status_code == 200, response.status_code
    assert b"User Management" in response.content

    response = client.post(reverse("inventory:user_create"), {
        "username": "switchmap_phase32_user",
        "first_name": "Phase",
        "last_name": "ThirtyTwo",
        "email": "phase32@example.local",
        "role": ROLE_OPERATOR,
        "is_active": "on",
        "password1": "Phase32UserPass!",
        "password2": "Phase32UserPass!",
    })
    assert response.status_code == 302, response.status_code
    target = User.objects.get(username="switchmap_phase32_user")
    assert user_role(target) == ROLE_OPERATOR

    response = client.post(reverse("inventory:user_edit", args=[target.id]), {
        "username": "switchmap_phase32_user",
        "first_name": "Phase",
        "last_name": "ThirtyTwoUpdated",
        "email": "phase32-updated@example.local",
        "role": ROLE_ADMIN,
        "is_active": "on",
        "is_staff": "on",
    })
    assert response.status_code == 302, response.status_code
    target.refresh_from_db()
    assert target.email == "phase32-updated@example.local"
    assert target.is_staff is True
    assert user_role(target) == ROLE_ADMIN

    response = client.post(reverse("inventory:user_password", args=[target.id]), {
        "password1": "Phase32NewPass!",
        "password2": "Phase32NewPass!",
    })
    assert response.status_code == 302, response.status_code
    target.refresh_from_db()
    assert target.check_password("Phase32NewPass!")

    assert SystemAuditLog.objects.filter(action="user_create", target_username="switchmap_phase32_user").exists()
    assert SystemAuditLog.objects.filter(action="user_update", target_username="switchmap_phase32_user").exists()
    assert SystemAuditLog.objects.filter(action="user_password_change", target_username="switchmap_phase32_user").exists()

    client.force_login(viewer)
    response = client.get(reverse("inventory:user_management"))
    assert response.status_code == 403, response.status_code

    print("PHASE32_USER_MANAGEMENT_OK")


if __name__ == "__main__":
    main()
