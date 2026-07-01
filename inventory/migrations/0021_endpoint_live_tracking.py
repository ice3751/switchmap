from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0020_alarm_engine_v2"),
    ]

    operations = [
        migrations.CreateModel(
            name="NetworkEndpoint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("identity_key", models.CharField(max_length=180, unique=True)),
                ("mac_address", models.CharField(db_index=True, max_length=32)),
                ("ip_address", models.GenericIPAddressField(blank=True, db_index=True, null=True)),
                ("vlan", models.PositiveIntegerField(blank=True, db_index=True, null=True)),
                ("hostname", models.CharField(blank=True, db_index=True, max_length=255)),
                ("vendor", models.CharField(blank=True, max_length=120)),
                ("connection_type", models.CharField(choices=[("direct_port", "Direct Port"), ("behind_ap", "Behind AP"), ("behind_router", "Behind Router"), ("behind_trunk", "Behind Trunk"), ("behind_network_device", "Behind Network Device"), ("unknown", "Unknown"), ("conflict", "Conflict")], db_index=True, default="unknown", max_length=40)),
                ("status", models.CharField(choices=[("active", "Active"), ("stale", "Stale"), ("missing", "Missing")], db_index=True, default="active", max_length=20)),
                ("confidence", models.PositiveSmallIntegerField(default=50)),
                ("via_device_name", models.CharField(blank=True, max_length=200)),
                ("ssid", models.CharField(blank=True, max_length=150)),
                ("sources", models.TextField(blank=True)),
                ("evidence_summary", models.TextField(blank=True)),
                ("first_seen", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_seen", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("last_seen_port", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="endpoint_last_seen_ports", to="inventory.port")),
                ("last_seen_switch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="endpoint_last_seen_switches", to="inventory.switch")),
                ("via_device", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="endpoint_via_devices", to="inventory.switch")),
            ],
            options={
                "ordering": ["-last_seen", "mac_address", "ip_address"],
            },
        ),
        migrations.CreateModel(
            name="EndpointObservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("observed_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("source", models.CharField(db_index=True, max_length=80)),
                ("mac_address", models.CharField(db_index=True, max_length=32)),
                ("ip_address", models.GenericIPAddressField(blank=True, db_index=True, null=True)),
                ("vlan", models.PositiveIntegerField(blank=True, db_index=True, null=True)),
                ("connection_type", models.CharField(db_index=True, max_length=40)),
                ("confidence", models.PositiveSmallIntegerField(default=50)),
                ("source_device_name", models.CharField(blank=True, max_length=200)),
                ("source_interface", models.CharField(blank=True, max_length=120)),
                ("source_detail", models.CharField(blank=True, max_length=255)),
                ("raw_data", models.TextField(blank=True)),
                ("is_selected", models.BooleanField(default=False)),
                ("endpoint", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="observations", to="inventory.networkendpoint")),
                ("port", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="endpoint_observations", to="inventory.port")),
                ("switch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="endpoint_observations", to="inventory.switch")),
            ],
            options={
                "ordering": ["-observed_at", "mac_address", "ip_address"],
            },
        ),
        migrations.AddIndex(model_name="networkendpoint", index=models.Index(fields=["mac_address", "ip_address"], name="ep_mac_ip_idx")),
        migrations.AddIndex(model_name="networkendpoint", index=models.Index(fields=["vlan", "last_seen"], name="ep_vlan_seen_idx")),
        migrations.AddIndex(model_name="networkendpoint", index=models.Index(fields=["connection_type", "last_seen"], name="ep_conn_seen_idx")),
        migrations.AddIndex(model_name="networkendpoint", index=models.Index(fields=["last_seen_switch", "last_seen"], name="ep_sw_seen_idx")),
        migrations.AddIndex(model_name="networkendpoint", index=models.Index(fields=["last_seen_port", "last_seen"], name="ep_port_seen_idx")),
        migrations.AddIndex(model_name="networkendpoint", index=models.Index(fields=["status", "is_active"], name="ep_status_active_idx")),
        migrations.AddIndex(model_name="endpointobservation", index=models.Index(fields=["mac_address", "ip_address", "-observed_at"], name="epo_mac_ip_obs_idx")),
        migrations.AddIndex(model_name="endpointobservation", index=models.Index(fields=["vlan", "-observed_at"], name="epo_vlan_obs_idx")),
        migrations.AddIndex(model_name="endpointobservation", index=models.Index(fields=["switch", "-observed_at"], name="epo_sw_obs_idx")),
        migrations.AddIndex(model_name="endpointobservation", index=models.Index(fields=["port", "-observed_at"], name="epo_port_obs_idx")),
        migrations.AddIndex(model_name="endpointobservation", index=models.Index(fields=["connection_type", "-observed_at"], name="epo_conn_obs_idx")),
        migrations.AddIndex(model_name="endpointobservation", index=models.Index(fields=["source", "-observed_at"], name="epo_source_obs_idx")),
    ]
