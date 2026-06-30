# Generated manually for SwitchMap Phase 77.

import django.db.models.deletion
from django.db import migrations, models


def seed_default_job_templates(apps, schema_editor):
    SSHJobTemplate = apps.get_model("inventory", "SSHJobTemplate")
    defaults = [
        ("Access VLAN Change", "set_access_vlan", "100", "medium", True, "تغییر VLAN دسترسی با Preview قبل از اجرا."),
        ("Set Port Description", "set_description", "SWITCHMAP-{interface}", "low", False, "ثبت Description استاندارد برای پورت."),
        ("Safe No Shutdown", "no_shutdown", "", "medium", True, "فعال‌سازی پورت بعد از بررسی."),
        ("PoE Off", "poe_never", "", "high", True, "قطع PoE؛ فقط بعد از تأیید."),
    ]
    for name, action, value_template, risk_level, requires_approval, description in defaults:
        SSHJobTemplate.objects.get_or_create(
            name=name,
            defaults={
                "action": action,
                "value_template": value_template,
                "risk_level": risk_level,
                "requires_approval": requires_approval,
                "description": description,
                "is_active": True,
                "created_by": "phase77_migration",
                "updated_by": "phase77_migration",
            },
        )


def unseed_default_job_templates(apps, schema_editor):
    SSHJobTemplate = apps.get_model("inventory", "SSHJobTemplate")
    SSHJobTemplate.objects.filter(created_by="phase77_migration").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0017_phase55_mikrotik_data_foundation"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="port",
            index=models.Index(fields=["description"], name="p77_port_desc_idx"),
        ),
        migrations.AddIndex(
            model_name="port",
            index=models.Index(fields=["cable_label"], name="p77_port_cable_idx"),
        ),
        migrations.AddIndex(
            model_name="port",
            index=models.Index(fields=["interface_name"], name="p77_port_iface_idx"),
        ),
        migrations.AddIndex(
            model_name="port",
            index=models.Index(fields=["status"], name="p77_port_status_idx"),
        ),
        migrations.AddIndex(
            model_name="port",
            index=models.Index(fields=["port_mode"], name="p77_port_mode_idx"),
        ),
        migrations.AddIndex(
            model_name="port",
            index=models.Index(fields=["documentation_status"], name="p77_port_doc_idx"),
        ),
        migrations.AddIndex(
            model_name="port",
            index=models.Index(fields=["owner"], name="p77_port_owner_idx"),
        ),
        migrations.AddIndex(
            model_name="port",
            index=models.Index(fields=["asset_tag"], name="p77_port_asset_idx"),
        ),
        migrations.AddIndex(
            model_name="switch",
            index=models.Index(fields=["is_active", "topology_position"], name="p77_sw_active_pos_idx"),
        ),
        migrations.AddIndex(
            model_name="switch",
            index=models.Index(fields=["device_family", "is_active"], name="p77_sw_family_active_idx"),
        ),
        migrations.AddIndex(
            model_name="switch",
            index=models.Index(fields=["device_role", "is_active"], name="p77_sw_role_active_idx"),
        ),
        migrations.CreateModel(
            name="SSHJobTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=140, unique=True)),
                ("action", models.CharField(max_length=60)),
                ("value_template", models.CharField(blank=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("risk_level", models.CharField(choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")], default="medium", max_length=20)),
                ("requires_approval", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_by", models.CharField(blank=True, max_length=150)),
                ("updated_by", models.CharField(blank=True, max_length=150)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["risk_level", "name"],
                "indexes": [
                    models.Index(fields=["action", "is_active"], name="p77_job_action_active_idx"),
                    models.Index(fields=["risk_level", "is_active"], name="p77_job_risk_active_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ConfigBackupSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor_username", models.CharField(blank=True, max_length=150)),
                ("command_source", models.CharField(choices=[("manual", "Manual Paste"), ("ssh", "SSH"), ("scheduled", "Scheduled"), ("imported", "Imported")], default="manual", max_length=30)),
                ("config_type", models.CharField(choices=[("running", "Running Config"), ("startup", "Startup Config"), ("export", "Export"), ("other", "Other")], default="running", max_length=30)),
                ("command", models.CharField(blank=True, default="show running-config", max_length=150)),
                ("content_hash", models.CharField(db_index=True, max_length=64)),
                ("content", models.TextField()),
                ("diff_text", models.TextField(blank=True)),
                ("note", models.TextField(blank=True)),
                ("switch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="config_backup_snapshots", to="inventory.switch")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["switch", "-created_at"], name="p77_cfg_switch_created_idx"),
                    models.Index(fields=["config_type", "-created_at"], name="p77_cfg_type_created_idx"),
                    models.Index(fields=["actor_username", "-created_at"], name="p77_cfg_actor_created_idx"),
                ],
            },
        ),
        migrations.RunPython(seed_default_job_templates, unseed_default_job_templates),
    ]
