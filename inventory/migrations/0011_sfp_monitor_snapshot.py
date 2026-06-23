from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0010_cisco_syslog_entry"),
    ]

    operations = [
        migrations.CreateModel(
            name="SfpMonitorSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("interface_name", models.CharField(max_length=80)),
                ("poll_time", models.DateTimeField(auto_now_add=True)),
                ("link_status", models.CharField(blank=True, max_length=80)),
                ("vlan_text", models.CharField(blank=True, max_length=80)),
                ("duplex", models.CharField(blank=True, max_length=30)),
                ("speed", models.CharField(blank=True, max_length=30)),
                ("media_type", models.CharField(blank=True, max_length=160)),
                ("err_disabled", models.BooleanField(default=False)),
                ("align_errors", models.BigIntegerField(default=0)),
                ("fcs_errors", models.BigIntegerField(default=0)),
                ("xmit_errors", models.BigIntegerField(default=0)),
                ("rcv_errors", models.BigIntegerField(default=0)),
                ("input_errors", models.BigIntegerField(default=0)),
                ("output_errors", models.BigIntegerField(default=0)),
                ("out_discards", models.BigIntegerField(default=0)),
                ("align_delta", models.BigIntegerField(default=0)),
                ("fcs_delta", models.BigIntegerField(default=0)),
                ("xmit_delta", models.BigIntegerField(default=0)),
                ("rcv_delta", models.BigIntegerField(default=0)),
                ("input_error_delta", models.BigIntegerField(default=0)),
                ("output_error_delta", models.BigIntegerField(default=0)),
                ("out_discard_delta", models.BigIntegerField(default=0)),
                ("temperature_c", models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
                ("voltage_v", models.DecimalField(blank=True, decimal_places=3, max_digits=7, null=True)),
                ("current_ma", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("tx_power_dbm", models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
                ("rx_power_dbm", models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
                ("health_state", models.CharField(choices=[("healthy", "Healthy"), ("warning", "Warning"), ("critical", "Critical"), ("unknown", "Unknown")], default="unknown", max_length=20)),
                ("health_note", models.CharField(blank=True, max_length=255)),
                ("raw_status_line", models.TextField(blank=True)),
                ("port", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sfp_monitor_snapshots", to="inventory.port")),
                ("switch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sfp_monitor_snapshots", to="inventory.switch")),
            ],
            options={
                "ordering": ["-poll_time", "switch", "interface_name"],
                "indexes": [
                    models.Index(fields=["switch", "interface_name", "-poll_time"], name="sfp_sw_if_poll_idx"),
                    models.Index(fields=["health_state", "-poll_time"], name="sfp_health_poll_idx"),
                    models.Index(fields=["err_disabled", "-poll_time"], name="sfp_errdis_poll_idx"),
                ],
            },
        ),
    ]
