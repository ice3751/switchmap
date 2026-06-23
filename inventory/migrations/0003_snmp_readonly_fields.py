from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_enrich_port_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="switch",
            name="snmp_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="switch",
            name="snmp_community",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="switch",
            name="snmp_port",
            field=models.PositiveIntegerField(default=161),
        ),
        migrations.AddField(
            model_name="switch",
            name="snmp_timeout",
            field=models.PositiveSmallIntegerField(default=2),
        ),
        migrations.AddField(
            model_name="switch",
            name="snmp_last_poll",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="switch",
            name="snmp_last_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="port",
            name="snmp_if_index",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="port",
            name="snmp_raw_name",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="port",
            name="snmp_alias",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="port",
            name="snmp_admin_status",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="port",
            name="snmp_oper_status",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="port",
            name="snmp_speed_mbps",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="port",
            name="snmp_last_poll",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
