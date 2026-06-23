from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0005_vlan_port_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="port",
            name="native_vlan",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="port",
            name="poe_admin_status",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="port",
            name="poe_detection_status",
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
