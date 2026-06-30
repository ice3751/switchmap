from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0008_port_action_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="portactionlog",
            name="actor_username",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="portactionlog",
            name="client_ip",
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portactionlog",
            name="request_path",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="portactionlog",
            name="action_label",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddIndex(
            model_name="portactionlog",
            index=models.Index(fields=["-created_at"], name="pal_created_idx"),
        ),
        migrations.AddIndex(
            model_name="portactionlog",
            index=models.Index(fields=["switch", "-created_at"], name="pal_switch_created_idx"),
        ),
        migrations.AddIndex(
            model_name="portactionlog",
            index=models.Index(fields=["success", "-created_at"], name="pal_success_created_idx"),
        ),
    ]
