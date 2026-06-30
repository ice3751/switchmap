from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0004_discovery_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="port",
            name="port_mode",
            field=models.CharField(
                choices=[
                    ("unknown", "نامشخص"),
                    ("access", "Access"),
                    ("trunk", "Trunk"),
                ],
                default="unknown",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="port",
            name="access_vlan",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="port",
            name="voice_vlan",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="port",
            name="trunk_vlans",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
