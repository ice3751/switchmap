import os
from pathlib import Path

from switchmap_smoke import read_static_css

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.test import Client, override_settings
from django.contrib.auth import get_user_model

django.setup()


def main():
    User = get_user_model()
    user, _ = User.objects.get_or_create(username="switchmap_phase35_1_admin", defaults={"is_staff": True, "is_superuser": True})
    user.is_staff = True
    user.is_superuser = True
    user.set_password("SwitchMapTest!35")
    user.save()

    client = Client(HTTP_HOST="127.0.0.1")
    assert client.login(username="switchmap_phase35_1_admin", password="SwitchMapTest!35")
    response = client.get("/")
    assert response.status_code == 200, response.status_code
    html = response.content.decode("utf-8")
    assert "nav-link-notification" in html
    assert "sidebar-notification-box" not in html
    assert "alarm-mini-dropdown" in html
    assert "SFP Live" in html

    css = read_static_css()
    assert "Phase 35.1 - notification UI cleanup" in css
    print("PHASE35_1_NOTIFICATION_UI_OK")


if __name__ == "__main__":
    with override_settings(ALLOWED_HOSTS=["127.0.0.1", "localhost", "testserver"]):
        main()
