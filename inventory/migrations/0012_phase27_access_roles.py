from django.db import migrations, models


ROLE_NAMES = ["View Only", "Operator", "Admin"]


def create_access_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for role_name in ROLE_NAMES:
        Group.objects.get_or_create(name=role_name)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0011_sfp_monitor_snapshot"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="portactionlog",
            name="actor_role",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.RunPython(create_access_groups, noop_reverse),
    ]
