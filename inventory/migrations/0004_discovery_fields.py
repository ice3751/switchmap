from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0003_snmp_readonly_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="switch",
            name="discovery_last_poll",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="switch",
            name="discovery_last_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="port",
            name="neighbor_source",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="port",
            name="neighbor_device",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="port",
            name="neighbor_port",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="port",
            name="neighbor_ip",
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="port",
            name="mac_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="port",
            name="mac_addresses",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="port",
            name="discovery_last_poll",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
