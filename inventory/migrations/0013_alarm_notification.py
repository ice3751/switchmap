from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0012_phase27_access_roles"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlarmNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fingerprint", models.CharField(max_length=220, unique=True)),
                ("source", models.CharField(blank=True, max_length=80)),
                ("category", models.CharField(choices=[("snmp", "SNMP"), ("sfp", "SFP"), ("interface", "Interface"), ("topology", "Topology"), ("system", "System")], default="system", max_length=30)),
                ("severity", models.CharField(choices=[("info", "Info"), ("warning", "Warning"), ("critical", "Critical")], default="warning", max_length=20)),
                ("status", models.CharField(choices=[("active", "Active"), ("acknowledged", "Acknowledged"), ("resolved", "Resolved")], default="active", max_length=20)),
                ("title", models.CharField(max_length=180)),
                ("message", models.TextField(blank=True)),
                ("details", models.TextField(blank=True)),
                ("first_seen", models.DateTimeField(auto_now_add=True)),
                ("last_seen", models.DateTimeField(auto_now=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("acknowledged_by", models.CharField(blank=True, max_length=150)),
                ("occurrences", models.PositiveIntegerField(default=1)),
                ("port", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="alarms", to="inventory.port")),
                ("switch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="alarms", to="inventory.switch")),
            ],
            options={
                "ordering": ["-last_seen", "severity", "category"],
                "indexes": [
                    models.Index(fields=["status", "severity", "-last_seen"], name="alarm_status_sev_seen_idx"),
                    models.Index(fields=["switch", "status", "-last_seen"], name="alarm_switch_status_idx"),
                    models.Index(fields=["category", "status", "-last_seen"], name="alarm_cat_status_idx"),
                ],
            },
        ),
    ]
