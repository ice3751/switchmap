from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0007_switch_ssh_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortActionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=50)),
                ("value", models.CharField(blank=True, max_length=100)),
                ("ssh_username", models.CharField(blank=True, max_length=100)),
                ("success", models.BooleanField(default=False)),
                ("message", models.TextField(blank=True)),
                ("commands", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("port", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="action_logs", to="inventory.port")),
                ("switch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="port_action_logs", to="inventory.switch")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
