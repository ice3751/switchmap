from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0009_audit_log_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="CiscoSyslogEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("event_time_text", models.CharField(blank=True, max_length=120)),
                ("source_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("facility", models.CharField(blank=True, max_length=80)),
                ("severity", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("severity_name", models.CharField(blank=True, max_length=30)),
                ("mnemonic", models.CharField(blank=True, max_length=100)),
                ("category", models.CharField(choices=[("interface", "Interface / Link"), ("security", "Security / Login / AAA"), ("config", "Configuration"), ("stp", "STP / Loop / Topology"), ("vlan", "VLAN / Trunk"), ("poe", "PoE / Power"), ("environment", "Environment / Power / Fan"), ("stack", "Stack / Module"), ("routing", "Routing"), ("protocol", "CDP / LLDP / SNMP"), ("dhcp", "DHCP / IP"), ("system", "System"), ("other", "Other")], default="other", max_length=30)),
                ("interface_name", models.CharField(blank=True, max_length=80)),
                ("message", models.TextField(blank=True)),
                ("raw_line", models.TextField()),
                ("is_parsed", models.BooleanField(default=False)),
                ("switch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cisco_syslog_entries", to="inventory.switch")),
            ],
            options={
                "ordering": ["-received_at"],
                "indexes": [models.Index(fields=["-received_at"], name="csl_received_idx"), models.Index(fields=["switch", "-received_at"], name="csl_switch_received_idx"), models.Index(fields=["severity", "-received_at"], name="csl_severity_received_idx"), models.Index(fields=["category", "-received_at"], name="csl_category_received_idx"), models.Index(fields=["facility", "-received_at"], name="csl_facility_received_idx")],
            },
        ),
    ]
