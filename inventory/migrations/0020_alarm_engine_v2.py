from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0019_phase79_port_connection_history"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlarmEvidence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fingerprint", models.CharField(db_index=True, max_length=220)),
                ("rule_key", models.CharField(db_index=True, max_length=80)),
                ("source", models.CharField(blank=True, max_length=80)),
                ("evidence_type", models.CharField(blank=True, max_length=80)),
                ("observed_at", models.DateTimeField(blank=True, null=True)),
                ("evidence_key", models.CharField(blank=True, max_length=255)),
                ("raw_value", models.TextField(blank=True)),
                ("previous_value", models.TextField(blank=True)),
                ("delta_value", models.TextField(blank=True)),
                ("threshold", models.CharField(blank=True, max_length=255)),
                ("admin_status", models.CharField(blank=True, max_length=80)),
                ("oper_status", models.CharField(blank=True, max_length=80)),
                ("link_status", models.CharField(blank=True, max_length=80)),
                ("topology_confidence", models.CharField(blank=True, max_length=40)),
                ("decision", models.CharField(choices=[("emit", "Emit"), ("pending", "Pending"), ("suppressed", "Suppressed"), ("resolved", "Resolved"), ("ignored", "Ignored")], default="pending", max_length=30)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("details", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("port", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="alarm_evidence", to="inventory.port")),
                ("switch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="alarm_evidence", to="inventory.switch")),
            ],
            options={
                "ordering": ["-observed_at", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AlarmPolicyState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fingerprint", models.CharField(max_length=220, unique=True)),
                ("rule_key", models.CharField(db_index=True, max_length=80)),
                ("state", models.CharField(choices=[("pending", "Pending"), ("active", "Active"), ("suppressed", "Suppressed"), ("resolved", "Resolved"), ("silenced", "Silenced")], default="pending", max_length=30)),
                ("last_evidence_key", models.CharField(blank=True, max_length=255)),
                ("current_failures", models.PositiveIntegerField(default=0)),
                ("occurrence_count_v2", models.PositiveIntegerField(default=0)),
                ("last_observed_at", models.DateTimeField(blank=True, null=True)),
                ("last_emitted_at", models.DateTimeField(blank=True, null=True)),
                ("last_resolved_at", models.DateTimeField(blank=True, null=True)),
                ("suppressed_reason", models.CharField(blank=True, max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["rule_key", "fingerprint"],
            },
        ),
        migrations.CreateModel(
            name="AlarmSilence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fingerprint", models.CharField(blank=True, db_index=True, max_length=220)),
                ("rule_key", models.CharField(blank=True, db_index=True, max_length=80)),
                ("reason", models.TextField(blank=True)),
                ("active", models.BooleanField(default=True)),
                ("created_by", models.CharField(blank=True, max_length=150)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("port", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="alarm_silences", to="inventory.port")),
                ("switch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="alarm_silences", to="inventory.switch")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(model_name="alarmevidence", index=models.Index(fields=["fingerprint", "-created_at"], name="ae_fp_created_idx")),
        migrations.AddIndex(model_name="alarmevidence", index=models.Index(fields=["rule_key", "decision", "-created_at"], name="ae_rule_decision_idx")),
        migrations.AddIndex(model_name="alarmevidence", index=models.Index(fields=["switch", "decision", "-created_at"], name="ae_switch_decision_idx")),
        migrations.AddIndex(model_name="alarmevidence", index=models.Index(fields=["port", "decision", "-created_at"], name="ae_port_decision_idx")),
        migrations.AddIndex(model_name="alarmpolicystate", index=models.Index(fields=["state", "rule_key"], name="aps_state_rule_idx")),
        migrations.AddIndex(model_name="alarmpolicystate", index=models.Index(fields=["rule_key", "updated_at"], name="aps_rule_updated_idx")),
        migrations.AddIndex(model_name="alarmsilence", index=models.Index(fields=["active", "fingerprint"], name="silence_active_fp_idx")),
        migrations.AddIndex(model_name="alarmsilence", index=models.Index(fields=["active", "rule_key"], name="silence_active_rule_idx")),
        migrations.AddIndex(model_name="alarmsilence", index=models.Index(fields=["switch", "active"], name="silence_switch_active_idx")),
        migrations.AddIndex(model_name="alarmsilence", index=models.Index(fields=["port", "active"], name="silence_port_active_idx")),
    ]
