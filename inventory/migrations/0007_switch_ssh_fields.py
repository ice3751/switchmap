from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0006_vlan_poe_fix_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="switch",
            name="ssh_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="switch",
            name="ssh_username",
            field=models.CharField(blank=True, default="admin", max_length=100),
        ),
        migrations.AddField(
            model_name="switch",
            name="ssh_port",
            field=models.PositiveIntegerField(default=22),
        ),
    ]
