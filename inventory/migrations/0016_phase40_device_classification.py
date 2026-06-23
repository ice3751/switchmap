from django.db import migrations, models


def classify_existing_switches(apps, schema_editor):
    Switch = apps.get_model("inventory", "Switch")
    for switch in Switch.objects.all():
        text = " ".join([
            switch.name or "",
            switch.model or "",
            switch.location or "",
        ]).lower()
        updates = {}
        if "nexus" in text or "n3k" in text:
            updates.update({
                "vendor": "cisco",
                "device_family": "cisco_nexus",
                "device_role": "core_switch",
                "topology_position": min(switch.topology_position or 100, 20),
            })
        elif "3850" in text or "catalyst" in text or "edari" in text:
            updates.update({
                "vendor": "cisco",
                "device_family": "cisco_3850",
                "device_role": "access_switch",
                "topology_position": max(switch.topology_position or 100, 100),
            })
        elif "mikrotik" in text or "routerboard" in text or "rb" in text or "crs" in text or "cap" in text or "hex" in text:
            updates.update({
                "vendor": "mikrotik",
                "device_family": "mikrotik_router",
                "device_role": "unknown",
                "topology_position": switch.topology_position or 80,
            })
        if updates:
            for key, value in updates.items():
                setattr(switch, key, value)
            switch.save(update_fields=list(updates.keys()))


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0015_asset_documentation"),
    ]

    operations = [
        migrations.AddField(
            model_name="switch",
            name="vendor",
            field=models.CharField(
                choices=[("cisco", "Cisco"), ("mikrotik", "MikroTik"), ("other", "Other")],
                default="cisco",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="switch",
            name="device_family",
            field=models.CharField(
                choices=[
                    ("cisco_3850", "Cisco 3850"),
                    ("cisco_nexus", "Cisco Nexus"),
                    ("mikrotik_router", "MikroTik Router"),
                    ("mikrotik_switch", "MikroTik Switch"),
                    ("mikrotik_ap", "MikroTik AP"),
                    ("other", "Other"),
                ],
                default="cisco_3850",
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name="switch",
            name="device_role",
            field=models.CharField(
                choices=[
                    ("core_router", "Core Router"),
                    ("core_switch", "Core Switch"),
                    ("edge_router", "Edge Router"),
                    ("remote_office", "Remote Office"),
                    ("access_point", "Access Point"),
                    ("access_switch", "Access Switch"),
                    ("distribution", "Distribution"),
                    ("unknown", "Unknown"),
                ],
                default="unknown",
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name="switch",
            name="site",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="switch",
            name="topology_position",
            field=models.PositiveSmallIntegerField(default=100),
        ),
        migrations.AddField(
            model_name="switch",
            name="winbox_port",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="switch",
            name="needs_review",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(classify_existing_switches, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name="switch",
            options={"ordering": ["topology_position", "name"]},
        ),
    ]
