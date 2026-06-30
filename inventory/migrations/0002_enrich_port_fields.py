from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="port",
            name="device_type",
            field=models.CharField(
                choices=[
                    ("unknown", "نامشخص"),
                    ("pc", "PC"),
                    ("phone", "VoIP Phone"),
                    ("camera", "Camera"),
                    ("access_point", "Access Point"),
                    ("printer", "Printer"),
                    ("server", "Server"),
                    ("switch", "Switch"),
                    ("uplink", "Uplink"),
                    ("other", "Other"),
                ],
                default="unknown",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="port",
            name="owner",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="port",
            name="ip_address",
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="port",
            name="mac_address",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="port",
            name="cable_label",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="port",
            name="prtg_url",
            field=models.URLField(blank=True),
        ),
    ]
