from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0013_alarm_notification"),
    ]

    operations = [
        migrations.CreateModel(
            name="SystemAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("user", "User"), ("system", "System"), ("security", "Security")], default="system", max_length=30)),
                ("action", models.CharField(max_length=80)),
                ("actor_username", models.CharField(blank=True, max_length=150)),
                ("actor_role", models.CharField(blank=True, max_length=50)),
                ("target_username", models.CharField(blank=True, max_length=150)),
                ("target_id", models.PositiveIntegerField(blank=True, null=True)),
                ("client_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("request_path", models.CharField(blank=True, max_length=255)),
                ("message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["category", "-created_at"], name="sysaudit_cat_created_idx"),
                    models.Index(fields=["actor_username", "-created_at"], name="sysaudit_actor_idx"),
                    models.Index(fields=["target_username", "-created_at"], name="sysaudit_target_idx"),
                ],
            },
        ),
    ]
