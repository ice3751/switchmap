from django.db import models
from django.utils import timezone


class Switch(models.Model):
    class Vendor(models.TextChoices):
        CISCO = "cisco", "Cisco"
        MIKROTIK = "mikrotik", "MikroTik"
        OTHER = "other", "Other"

    class DeviceFamily(models.TextChoices):
        CISCO_3850 = "cisco_3850", "Cisco 3850"
        CISCO_NEXUS = "cisco_nexus", "Cisco Nexus"
        MIKROTIK_ROUTER = "mikrotik_router", "MikroTik Router"
        MIKROTIK_SWITCH = "mikrotik_switch", "MikroTik Switch"
        MIKROTIK_AP = "mikrotik_ap", "MikroTik AP"
        OTHER = "other", "Other"

    class DeviceRole(models.TextChoices):
        CORE_ROUTER = "core_router", "Core Router"
        CORE_SWITCH = "core_switch", "Core Switch"
        EDGE_ROUTER = "edge_router", "Edge Router"
        REMOTE_OFFICE = "remote_office", "Remote Office"
        ACCESS_POINT = "access_point", "Access Point"
        ACCESS_SWITCH = "access_switch", "Access Switch"
        DISTRIBUTION = "distribution", "Distribution"
        UNKNOWN = "unknown", "Unknown"

    name = models.CharField(max_length=100, unique=True)
    management_ip = models.GenericIPAddressField(unique=True)
    model = models.CharField(max_length=100, default="Cisco Catalyst 3850")
    vendor = models.CharField(max_length=30, choices=Vendor.choices, default=Vendor.CISCO)
    device_family = models.CharField(max_length=40, choices=DeviceFamily.choices, default=DeviceFamily.CISCO_3850)
    device_role = models.CharField(max_length=40, choices=DeviceRole.choices, default=DeviceRole.UNKNOWN)
    site = models.CharField(max_length=120, blank=True)
    topology_position = models.PositiveSmallIntegerField(default=100)
    winbox_port = models.PositiveIntegerField(null=True, blank=True)
    needs_review = models.BooleanField(default=False)
    location = models.CharField(max_length=150, blank=True)
    port_count = models.PositiveSmallIntegerField(default=48)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    snmp_enabled = models.BooleanField(default=False)
    snmp_community = models.CharField(max_length=100, blank=True)
    snmp_port = models.PositiveIntegerField(default=161)
    snmp_timeout = models.PositiveSmallIntegerField(default=2)
    snmp_last_poll = models.DateTimeField(null=True, blank=True)
    snmp_last_error = models.TextField(blank=True)

    discovery_last_poll = models.DateTimeField(null=True, blank=True)
    discovery_last_error = models.TextField(blank=True)

    ssh_enabled = models.BooleanField(default=True)
    ssh_username = models.CharField(max_length=100, default="admin", blank=True)
    ssh_port = models.PositiveIntegerField(default=22)

    class Meta:
        ordering = ["topology_position", "name"]
        indexes = [
            models.Index(fields=["is_active", "topology_position"], name="p77_sw_active_pos_idx"),
            models.Index(fields=["device_family", "is_active"], name="p77_sw_family_active_idx"),
            models.Index(fields=["device_role", "is_active"], name="p77_sw_role_active_idx"),
        ]

    def __str__(self):
        return self.name


class Port(models.Model):
    class Status(models.TextChoices):
        UP = "up", "Up"
        DOWN = "down", "Down"
        DISABLED = "disabled", "Disabled"
        ERROR = "error", "Error"

    class DeviceType(models.TextChoices):
        UNKNOWN = "unknown", "نامشخص"
        PC = "pc", "PC"
        PHONE = "phone", "VoIP Phone"
        CAMERA = "camera", "Camera"
        ACCESS_POINT = "access_point", "Access Point"
        PRINTER = "printer", "Printer"
        SERVER = "server", "Server"
        SWITCH = "switch", "Switch"
        UPLINK = "uplink", "Uplink"
        OTHER = "other", "Other"

    class PortMode(models.TextChoices):
        UNKNOWN = "unknown", "نامشخص"
        ACCESS = "access", "Access"
        TRUNK = "trunk", "Trunk"

    class DocumentationStatus(models.TextChoices):
        UNDOCUMENTED = "undocumented", "Undocumented"
        PARTIAL = "partial", "Partial"
        DOCUMENTED = "documented", "Documented"
        NEEDS_REVIEW = "needs_review", "Needs Review"

    switch = models.ForeignKey(
        Switch,
        on_delete=models.CASCADE,
        related_name="ports",
    )
    interface_name = models.CharField(max_length=30)
    display_order = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=200, blank=True)
    connected_device = models.CharField(max_length=150, blank=True)
    device_type = models.CharField(
        max_length=30,
        choices=DeviceType.choices,
        default=DeviceType.UNKNOWN,
    )
    owner = models.CharField(max_length=150, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField(max_length=32, blank=True)
    vlan = models.PositiveSmallIntegerField(null=True, blank=True)
    port_mode = models.CharField(
        max_length=20,
        choices=PortMode.choices,
        default=PortMode.UNKNOWN,
    )
    access_vlan = models.PositiveIntegerField(null=True, blank=True)
    native_vlan = models.PositiveIntegerField(null=True, blank=True)
    voice_vlan = models.PositiveIntegerField(null=True, blank=True)
    trunk_vlans = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DOWN,
    )
    poe_enabled = models.BooleanField(default=False)
    poe_admin_status = models.CharField(max_length=50, blank=True)
    poe_detection_status = models.CharField(max_length=50, blank=True)
    room = models.CharField(max_length=100, blank=True)
    rack = models.CharField(max_length=80, blank=True)
    rack_unit = models.CharField(max_length=30, blank=True)
    patch_panel = models.CharField(max_length=100, blank=True)
    patch_panel_port = models.CharField(max_length=80, blank=True)
    outlet = models.CharField(max_length=100, blank=True)
    cable_label = models.CharField(max_length=100, blank=True)
    cable_type = models.CharField(max_length=60, blank=True)
    cable_length = models.CharField(max_length=60, blank=True)
    asset_tag = models.CharField(max_length=100, blank=True)
    documentation_status = models.CharField(
        max_length=30,
        choices=DocumentationStatus.choices,
        default=DocumentationStatus.UNDOCUMENTED,
    )
    prtg_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)

    snmp_if_index = models.PositiveIntegerField(null=True, blank=True)
    snmp_raw_name = models.CharField(max_length=100, blank=True)
    snmp_alias = models.CharField(max_length=200, blank=True)
    snmp_admin_status = models.CharField(max_length=30, blank=True)
    snmp_oper_status = models.CharField(max_length=30, blank=True)
    snmp_speed_mbps = models.PositiveIntegerField(null=True, blank=True)
    snmp_last_poll = models.DateTimeField(null=True, blank=True)

    neighbor_source = models.CharField(max_length=20, blank=True)
    neighbor_device = models.CharField(max_length=200, blank=True)
    neighbor_port = models.CharField(max_length=200, blank=True)
    neighbor_ip = models.GenericIPAddressField(null=True, blank=True)
    mac_count = models.PositiveSmallIntegerField(default=0)
    mac_addresses = models.TextField(blank=True)
    discovery_last_poll = models.DateTimeField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["switch", "display_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["switch", "interface_name"],
                name="unique_switch_interface",
            )
        ]
        indexes = [
            models.Index(fields=["description"], name="p77_port_desc_idx"),
            models.Index(fields=["cable_label"], name="p77_port_cable_idx"),
            models.Index(fields=["interface_name"], name="p77_port_iface_idx"),
            models.Index(fields=["status"], name="p77_port_status_idx"),
            models.Index(fields=["port_mode"], name="p77_port_mode_idx"),
            models.Index(fields=["documentation_status"], name="p77_port_doc_idx"),
            models.Index(fields=["owner"], name="p77_port_owner_idx"),
            models.Index(fields=["asset_tag"], name="p77_port_asset_idx"),
        ]


    def normalized_poe_admin(self):
        value = (self.poe_admin_status or "").strip().lower()
        mapping = {
            "enabled": "فعال",
            "enable": "فعال",
            "1": "فعال",
            "disabled": "غیرفعال",
            "disable": "غیرفعال",
            "2": "غیرفعال",
        }
        if value in mapping:
            return mapping[value]
        if self.poe_enabled:
            return "فعال"
        return self.poe_admin_status or "-"

    def normalized_poe_detection(self):
        value = (self.poe_detection_status or "").strip().lower()
        mapping = {
            "searching": "دستگاه پیدا نشد",
            "unknown": "نامشخص",
            "disabled": "غیرفعال",
            "delivering power": "در حال برق‌دهی",
            "fault": "خطا",
            "test": "تست",
            "other fault": "خطای دیگر",
            "1": "نامشخص",
            "2": "غیرفعال",
            "3": "دستگاه پیدا نشد",
            "4": "در حال برق‌دهی",
            "5": "خطا",
            "6": "تست",
            "7": "خطای دیگر",
        }
        return mapping.get(value, self.poe_detection_status or "-")

    def poe_summary(self):
        admin = self.normalized_poe_admin()
        detection = self.normalized_poe_detection()

        if admin == "غیرفعال":
            return "غیرفعال"
        if detection == "در حال برق‌دهی":
            return "فعال / برق‌دهی"
        if detection == "دستگاه پیدا نشد":
            return "فعال / دستگاه پیدا نشد"
        if detection == "-":
            return admin
        return f"{admin} / {detection}"

    def inferred_type(self):
        device_type = self.get_device_type_display()
        if self.device_type and self.device_type != self.DeviceType.UNKNOWN:
            return device_type

        text = " ".join([
            self.connected_device or "",
            self.description or "",
            self.snmp_alias or "",
            self.neighbor_device or "",
            self.neighbor_port or "",
        ]).lower()

        if self.port_mode == self.PortMode.TRUNK:
            return "Trunk"
        if self.neighbor_device:
            return "Network Device"
        if "camera" in text or "cam" in text or "hik" in text:
            return "Camera"
        if "phone" in text or "voip" in text or "sep" in text:
            return "VoIP Phone"
        if "ap" in text or "access point" in text or "cap" in text:
            return "Access Point"
        if "printer" in text or "print" in text:
            return "Printer"
        if self.mac_count == 0 and self.status == self.Status.DOWN:
            return "Unused"
        if self.mac_count > 1:
            return "Multi-MAC"
        if self.mac_count == 1:
            return "PC/Endpoint"
        return "نامشخص"

    def documentation_completeness_label(self):
        if self.documentation_status == self.DocumentationStatus.DOCUMENTED:
            return "کامل"
        if self.documentation_status == self.DocumentationStatus.NEEDS_REVIEW:
            return "نیازمند بررسی"
        if self.documentation_status == self.DocumentationStatus.PARTIAL:
            return "نیمه‌کامل"
        return "بدون مستندات"

    def __str__(self):
        return f"{self.switch.name} - {self.interface_name}"


class PortDocumentationHistory(models.Model):
    port = models.ForeignKey(
        Port,
        on_delete=models.CASCADE,
        related_name="documentation_history",
    )
    switch = models.ForeignKey(
        Switch,
        on_delete=models.CASCADE,
        related_name="port_documentation_history",
    )
    interface_name = models.CharField(max_length=80)
    changed_fields = models.CharField(max_length=500, blank=True)
    before_data = models.TextField(blank=True)
    after_data = models.TextField(blank=True)
    actor_username = models.CharField(max_length=150, blank=True)
    actor_role = models.CharField(max_length=50, blank=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    request_path = models.CharField(max_length=255, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["port", "-created_at"], name="pdh_port_created_idx"),
            models.Index(fields=["switch", "-created_at"], name="pdh_switch_created_idx"),
            models.Index(fields=["actor_username", "-created_at"], name="pdh_actor_created_idx"),
        ]

    def __str__(self):
        return f"{self.switch.name} {self.interface_name} documentation change"


class PortActionLog(models.Model):
    port = models.ForeignKey(
        Port,
        on_delete=models.CASCADE,
        related_name="action_logs",
    )
    switch = models.ForeignKey(
        Switch,
        on_delete=models.CASCADE,
        related_name="port_action_logs",
    )
    action = models.CharField(max_length=50)
    value = models.CharField(max_length=100, blank=True)
    ssh_username = models.CharField(max_length=100, blank=True)
    actor_username = models.CharField(max_length=150, blank=True)
    actor_role = models.CharField(max_length=50, blank=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    request_path = models.CharField(max_length=255, blank=True)
    action_label = models.CharField(max_length=100, blank=True)
    success = models.BooleanField(default=False)
    message = models.TextField(blank=True)
    commands = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"], name="pal_created_idx"),
            models.Index(fields=["switch", "-created_at"], name="pal_switch_created_idx"),
            models.Index(fields=["success", "-created_at"], name="pal_success_created_idx"),
        ]

    def result_label(self):
        return "موفق" if self.success else "ناموفق"

    def __str__(self):
        result = "OK" if self.success else "FAILED"
        return f"{self.switch.name} {self.port.interface_name} {self.action} {result}"



class PortConnectionHistory(models.Model):
    class EventType(models.TextChoices):
        SEEN = "seen", "Seen"
        UP = "up", "Up"
        DOWN = "down", "Down"
        CHANGE = "change", "Change"
        MANUAL = "manual", "Manual"

    port = models.ForeignKey(
        Port,
        on_delete=models.CASCADE,
        related_name="connection_history",
    )
    switch = models.ForeignKey(
        Switch,
        on_delete=models.CASCADE,
        related_name="port_connection_history",
    )
    interface_name = models.CharField(max_length=80)
    event_type = models.CharField(max_length=20, choices=EventType.choices, default=EventType.SEEN)
    status_before = models.CharField(max_length=30, blank=True)
    status_after = models.CharField(max_length=30, blank=True)
    observed_at = models.DateTimeField(default=timezone.now)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    occurrence_count = models.PositiveIntegerField(default=1)

    neighbor_source = models.CharField(max_length=30, blank=True)
    neighbor_device = models.CharField(max_length=200, blank=True)
    neighbor_port = models.CharField(max_length=200, blank=True)
    neighbor_ip = models.GenericIPAddressField(null=True, blank=True)
    connected_device = models.CharField(max_length=150, blank=True)
    device_type = models.CharField(max_length=30, blank=True)
    owner = models.CharField(max_length=150, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField(max_length=32, blank=True)
    mac_addresses = models.TextField(blank=True)
    mac_count = models.PositiveSmallIntegerField(default=0)

    description = models.CharField(max_length=200, blank=True)
    snmp_alias = models.CharField(max_length=200, blank=True)
    vlan = models.PositiveSmallIntegerField(null=True, blank=True)
    port_mode = models.CharField(max_length=20, blank=True)
    access_vlan = models.PositiveIntegerField(null=True, blank=True)
    native_vlan = models.PositiveIntegerField(null=True, blank=True)
    voice_vlan = models.PositiveIntegerField(null=True, blank=True)
    trunk_vlans = models.CharField(max_length=255, blank=True)

    source = models.CharField(max_length=80, blank=True)
    note = models.TextField(blank=True)
    identity_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-observed_at", "-id"]
        indexes = [
            models.Index(fields=["port", "-observed_at"], name="pch_port_obs_idx"),
            models.Index(fields=["switch", "-observed_at"], name="pch_sw_obs_idx"),
            models.Index(fields=["event_type", "-observed_at"], name="pch_event_obs_idx"),
            models.Index(fields=["status_after", "-observed_at"], name="pch_status_obs_idx"),
            models.Index(fields=["port", "identity_hash"], name="pch_port_hash_idx"),
        ]

    def identity_label(self):
        if self.connected_device:
            return self.connected_device
        if self.neighbor_device:
            return self.neighbor_device
        if self.mac_address:
            return self.mac_address
        if self.mac_addresses:
            return self.mac_addresses.splitlines()[0]
        return "-"

    def __str__(self):
        return f"{self.switch.name} {self.interface_name} {self.event_type}"

class CiscoSyslogEntry(models.Model):
    SEVERITY_LABELS = {
        0: "Emergency",
        1: "Alert",
        2: "Critical",
        3: "Error",
        4: "Warning",
        5: "Notification",
        6: "Informational",
        7: "Debug",
    }

    CATEGORY_CHOICES = (
        ("interface", "Interface / Link"),
        ("security", "Security / Login / AAA"),
        ("config", "Configuration"),
        ("stp", "STP / Loop / Topology"),
        ("vlan", "VLAN / Trunk"),
        ("poe", "PoE / Power"),
        ("environment", "Environment / Power / Fan"),
        ("stack", "Stack / Module"),
        ("routing", "Routing"),
        ("protocol", "CDP / LLDP / SNMP"),
        ("dhcp", "DHCP / IP"),
        ("system", "System"),
        ("other", "Other"),
    )

    switch = models.ForeignKey(
        Switch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cisco_syslog_entries",
    )
    received_at = models.DateTimeField(auto_now_add=True)
    event_time_text = models.CharField(max_length=120, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    facility = models.CharField(max_length=80, blank=True)
    severity = models.PositiveSmallIntegerField(null=True, blank=True)
    severity_name = models.CharField(max_length=30, blank=True)
    mnemonic = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="other")
    interface_name = models.CharField(max_length=80, blank=True)
    message = models.TextField(blank=True)
    raw_line = models.TextField()
    is_parsed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["-received_at"], name="csl_received_idx"),
            models.Index(fields=["switch", "-received_at"], name="csl_switch_received_idx"),
            models.Index(fields=["severity", "-received_at"], name="csl_severity_received_idx"),
            models.Index(fields=["category", "-received_at"], name="csl_category_received_idx"),
            models.Index(fields=["facility", "-received_at"], name="csl_facility_received_idx"),
        ]

    def severity_label(self):
        if self.severity is None:
            return "-"
        return self.severity_name or self.SEVERITY_LABELS.get(self.severity, str(self.severity))

    def __str__(self):
        switch_name = self.switch.name if self.switch else str(self.source_ip or "Cisco")
        code = f"{self.facility}-{self.severity}-{self.mnemonic}" if self.is_parsed else "UNPARSED"
        return f"{switch_name} {code}"



class SfpMonitorSnapshot(models.Model):
    class Health(models.TextChoices):
        HEALTHY = "healthy", "Healthy"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"
        UNKNOWN = "unknown", "Unknown"

    switch = models.ForeignKey(
        Switch,
        on_delete=models.CASCADE,
        related_name="sfp_monitor_snapshots",
    )
    port = models.ForeignKey(
        Port,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sfp_monitor_snapshots",
    )
    interface_name = models.CharField(max_length=80)
    poll_time = models.DateTimeField(auto_now_add=True)
    link_status = models.CharField(max_length=80, blank=True)
    vlan_text = models.CharField(max_length=80, blank=True)
    duplex = models.CharField(max_length=30, blank=True)
    speed = models.CharField(max_length=30, blank=True)
    media_type = models.CharField(max_length=160, blank=True)
    err_disabled = models.BooleanField(default=False)

    align_errors = models.BigIntegerField(default=0)
    fcs_errors = models.BigIntegerField(default=0)
    xmit_errors = models.BigIntegerField(default=0)
    rcv_errors = models.BigIntegerField(default=0)
    input_errors = models.BigIntegerField(default=0)
    output_errors = models.BigIntegerField(default=0)
    out_discards = models.BigIntegerField(default=0)

    align_delta = models.BigIntegerField(default=0)
    fcs_delta = models.BigIntegerField(default=0)
    xmit_delta = models.BigIntegerField(default=0)
    rcv_delta = models.BigIntegerField(default=0)
    input_error_delta = models.BigIntegerField(default=0)
    output_error_delta = models.BigIntegerField(default=0)
    out_discard_delta = models.BigIntegerField(default=0)

    temperature_c = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    voltage_v = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    current_ma = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    tx_power_dbm = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    rx_power_dbm = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)

    health_state = models.CharField(max_length=20, choices=Health.choices, default=Health.UNKNOWN)
    health_note = models.CharField(max_length=255, blank=True)
    raw_status_line = models.TextField(blank=True)

    class Meta:
        ordering = ["-poll_time", "switch", "interface_name"]
        indexes = [
            models.Index(fields=["switch", "interface_name", "-poll_time"], name="sfp_sw_if_poll_idx"),
            models.Index(fields=["health_state", "-poll_time"], name="sfp_health_poll_idx"),
            models.Index(fields=["err_disabled", "-poll_time"], name="sfp_errdis_poll_idx"),
        ]

    def __str__(self):
        return f"{self.switch.name} {self.interface_name} {self.health_state}"


class AlarmNotification(models.Model):
    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"

    class Category(models.TextChoices):
        SNMP = "snmp", "SNMP"
        SFP = "sfp", "SFP"
        INTERFACE = "interface", "Interface"
        TOPOLOGY = "topology", "Topology"
        SYSTEM = "system", "System"

    switch = models.ForeignKey(
        Switch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alarms",
    )
    port = models.ForeignKey(
        Port,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alarms",
    )
    fingerprint = models.CharField(max_length=220, unique=True)
    source = models.CharField(max_length=80, blank=True)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.SYSTEM)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.WARNING)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    title = models.CharField(max_length=180)
    message = models.TextField(blank=True)
    details = models.TextField(blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.CharField(max_length=150, blank=True)
    occurrences = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-last_seen", "severity", "category"]
        indexes = [
            models.Index(fields=["status", "severity", "-last_seen"], name="alarm_status_sev_seen_idx"),
            models.Index(fields=["switch", "status", "-last_seen"], name="alarm_switch_status_idx"),
            models.Index(fields=["category", "status", "-last_seen"], name="alarm_cat_status_idx"),
        ]

    def status_label(self):
        return self.get_status_display()

    def severity_label(self):
        return self.get_severity_display()

    def __str__(self):
        target = self.switch.name if self.switch else "SwitchMap"
        if self.port:
            target = f"{target} {self.port.interface_name}"
        return f"{self.title} - {target}"


class AlarmEvidence(models.Model):
    class Decision(models.TextChoices):
        EMIT = "emit", "Emit"
        PENDING = "pending", "Pending"
        SUPPRESSED = "suppressed", "Suppressed"
        RESOLVED = "resolved", "Resolved"
        IGNORED = "ignored", "Ignored"

    fingerprint = models.CharField(max_length=220, db_index=True)
    rule_key = models.CharField(max_length=80, db_index=True)
    source = models.CharField(max_length=80, blank=True)
    switch = models.ForeignKey(
        Switch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alarm_evidence",
    )
    port = models.ForeignKey(
        Port,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alarm_evidence",
    )
    evidence_type = models.CharField(max_length=80, blank=True)
    observed_at = models.DateTimeField(null=True, blank=True)
    evidence_key = models.CharField(max_length=255, blank=True)
    raw_value = models.TextField(blank=True)
    previous_value = models.TextField(blank=True)
    delta_value = models.TextField(blank=True)
    threshold = models.CharField(max_length=255, blank=True)
    admin_status = models.CharField(max_length=80, blank=True)
    oper_status = models.CharField(max_length=80, blank=True)
    link_status = models.CharField(max_length=80, blank=True)
    topology_confidence = models.CharField(max_length=40, blank=True)
    decision = models.CharField(max_length=30, choices=Decision.choices, default=Decision.PENDING)
    reason = models.CharField(max_length=255, blank=True)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-observed_at", "-created_at"]
        indexes = [
            models.Index(fields=["fingerprint", "-created_at"], name="ae_fp_created_idx"),
            models.Index(fields=["rule_key", "decision", "-created_at"], name="ae_rule_decision_idx"),
            models.Index(fields=["switch", "decision", "-created_at"], name="ae_switch_decision_idx"),
            models.Index(fields=["port", "decision", "-created_at"], name="ae_port_decision_idx"),
        ]

    def __str__(self):
        return f"{self.rule_key} {self.fingerprint} {self.decision}"


class AlarmPolicyState(models.Model):
    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        SUPPRESSED = "suppressed", "Suppressed"
        RESOLVED = "resolved", "Resolved"
        SILENCED = "silenced", "Silenced"

    fingerprint = models.CharField(max_length=220, unique=True)
    rule_key = models.CharField(max_length=80, db_index=True)
    state = models.CharField(max_length=30, choices=State.choices, default=State.PENDING)
    last_evidence_key = models.CharField(max_length=255, blank=True)
    current_failures = models.PositiveIntegerField(default=0)
    occurrence_count_v2 = models.PositiveIntegerField(default=0)
    last_observed_at = models.DateTimeField(null=True, blank=True)
    last_emitted_at = models.DateTimeField(null=True, blank=True)
    last_resolved_at = models.DateTimeField(null=True, blank=True)
    suppressed_reason = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["rule_key", "fingerprint"]
        indexes = [
            models.Index(fields=["state", "rule_key"], name="aps_state_rule_idx"),
            models.Index(fields=["rule_key", "updated_at"], name="aps_rule_updated_idx"),
        ]

    def __str__(self):
        return f"{self.rule_key} {self.fingerprint} {self.state}"


class AlarmSilence(models.Model):
    fingerprint = models.CharField(max_length=220, blank=True, db_index=True)
    rule_key = models.CharField(max_length=80, blank=True, db_index=True)
    switch = models.ForeignKey(
        Switch,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alarm_silences",
    )
    port = models.ForeignKey(
        Port,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alarm_silences",
    )
    reason = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_by = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["active", "fingerprint"], name="silence_active_fp_idx"),
            models.Index(fields=["active", "rule_key"], name="silence_active_rule_idx"),
            models.Index(fields=["switch", "active"], name="silence_switch_active_idx"),
            models.Index(fields=["port", "active"], name="silence_port_active_idx"),
        ]

    def __str__(self):
        return self.fingerprint or self.rule_key or str(self.switch_id or self.port_id or self.id)


class SystemAuditLog(models.Model):
    class Category(models.TextChoices):
        USER = "user", "User"
        SYSTEM = "system", "System"
        SECURITY = "security", "Security"

    category = models.CharField(max_length=30, choices=Category.choices, default=Category.SYSTEM)
    action = models.CharField(max_length=80)
    actor_username = models.CharField(max_length=150, blank=True)
    actor_role = models.CharField(max_length=50, blank=True)
    target_username = models.CharField(max_length=150, blank=True)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    request_path = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "-created_at"], name="sysaudit_cat_created_idx"),
            models.Index(fields=["actor_username", "-created_at"], name="sysaudit_actor_idx"),
            models.Index(fields=["target_username", "-created_at"], name="sysaudit_target_idx"),
        ]

    def __str__(self):
        return f"{self.category} {self.action} {self.target_username}"



class Site(models.Model):
    class Kind(models.TextChoices):
        HQ = "hq", "HQ"
        REMOTE = "remote", "Remote"
        HOME = "home", "Home"
        CLOUD = "cloud", "Cloud"
        WIRELESS = "wireless", "Wireless"
        UNKNOWN = "unknown", "Unknown"

    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=50, unique=True)
    kind = models.CharField(max_length=30, choices=Kind.choices, default=Kind.UNKNOWN)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kind", "name"]

    def __str__(self):
        return self.name


class WanLink(models.Model):
    class LinkType(models.TextChoices):
        STARLINK = "starlink", "Starlink"
        FIBER = "fiber", "Fiber"
        SIM = "sim", "SIM"
        VPS = "vps", "VPS"
        LOCAL_TRANSIT = "local_transit", "Local Transit"
        OTHER = "other", "Other"

    name = models.CharField(max_length=120, unique=True)
    switch = models.ForeignKey(
        Switch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wan_links",
    )
    site = models.ForeignKey(
        Site,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wan_links",
    )
    link_type = models.CharField(max_length=30, choices=LinkType.choices, default=LinkType.OTHER)
    provider = models.CharField(max_length=120, blank=True)
    interface_name = models.CharField(max_length=80, blank=True)
    public_ip = models.GenericIPAddressField(null=True, blank=True)
    local_ip = models.GenericIPAddressField(null=True, blank=True)
    purpose = models.CharField(max_length=180, blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["site__name", "switch__name", "name"]
        indexes = [
            models.Index(fields=["switch", "is_active"], name="wan_switch_active_idx"),
            models.Index(fields=["site", "is_active"], name="wan_site_active_idx"),
            models.Index(fields=["link_type", "is_active"], name="wan_type_active_idx"),
        ]

    def __str__(self):
        return self.name


class RouterTunnel(models.Model):
    class TunnelType(models.TextChoices):
        WIREGUARD = "wireguard", "WireGuard"
        L2TP_IPSEC = "l2tp_ipsec", "L2TP/IPsec"
        EOIP = "eoip", "EoIP"
        GRE = "gre", "GRE"
        OVPN = "ovpn", "OpenVPN"
        VPN_ENDPOINT = "vpn_endpoint", "VPN Endpoint"
        LOCAL_TRANSIT = "local_transit", "Local Transit"
        CAP_MANAGEMENT = "cap_management", "CAP Management"
        UNKNOWN = "unknown", "Unknown"

    class Status(models.TextChoices):
        UP = "up", "Up"
        DOWN = "down", "Down"
        WARNING = "warning", "Warning"
        UNKNOWN = "unknown", "Unknown"

    class Confidence(models.TextChoices):
        DOCUMENTED = "documented", "Documented"
        INFERRED = "inferred", "Inferred"
        NEEDS_REVIEW = "needs_review", "Needs Review"

    name = models.CharField(max_length=140, unique=True)
    tunnel_type = models.CharField(max_length=30, choices=TunnelType.choices, default=TunnelType.UNKNOWN)
    source_switch = models.ForeignKey(
        Switch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbound_router_tunnels",
    )
    destination_switch = models.ForeignKey(
        Switch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inbound_router_tunnels",
    )
    source_site = models.ForeignKey(
        Site,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbound_router_tunnels",
    )
    destination_site = models.ForeignKey(
        Site,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inbound_router_tunnels",
    )
    local_tunnel_ip = models.GenericIPAddressField(null=True, blank=True)
    remote_tunnel_ip = models.GenericIPAddressField(null=True, blank=True)
    routed_networks = models.CharField(max_length=255, blank=True)
    failover_priority = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNKNOWN)
    confidence = models.CharField(max_length=30, choices=Confidence.choices, default=Confidence.INFERRED)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["failover_priority", "name"]
        indexes = [
            models.Index(fields=["source_switch", "is_active"], name="rt_src_switch_active_idx"),
            models.Index(fields=["destination_switch", "is_active"], name="rt_dst_switch_active_idx"),
            models.Index(fields=["tunnel_type", "status"], name="rt_type_status_idx"),
            models.Index(fields=["confidence", "is_active"], name="rt_conf_active_idx"),
        ]

    def status_label(self):
        return self.get_status_display()

    def type_label(self):
        return self.get_tunnel_type_display()

    def __str__(self):
        return self.name


class RoutingPolicy(models.Model):
    class PolicyType(models.TextChoices):
        IRAN = "iran", "Iran Traffic"
        FOREIGN = "foreign", "Foreign Traffic"
        SITE_TO_SITE = "site_to_site", "Site-to-Site"
        MANAGEMENT = "management", "Management"
        BACKUP = "backup", "Backup / Failover"
        DNS = "dns", "DNS / Split DNS"
        OTHER = "other", "Other"

    class Confidence(models.TextChoices):
        DOCUMENTED = "documented", "Documented"
        INFERRED = "inferred", "Inferred"
        NEEDS_REVIEW = "needs_review", "Needs Review"

    name = models.CharField(max_length=140, unique=True)
    switch = models.ForeignKey(
        Switch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routing_policies",
    )
    site = models.ForeignKey(
        Site,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routing_policies",
    )
    policy_type = models.CharField(max_length=30, choices=PolicyType.choices, default=PolicyType.OTHER)
    source_zone = models.CharField(max_length=120, blank=True)
    destination_zone = models.CharField(max_length=120, blank=True)
    preferred_path = models.CharField(max_length=180, blank=True)
    backup_path = models.CharField(max_length=180, blank=True)
    routing_table = models.CharField(max_length=100, blank=True)
    address_list = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    confidence = models.CharField(max_length=30, choices=Confidence.choices, default=Confidence.INFERRED)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["site__name", "switch__name", "policy_type", "name"]
        indexes = [
            models.Index(fields=["switch", "is_active"], name="rp_switch_active_idx"),
            models.Index(fields=["site", "is_active"], name="rp_site_active_idx"),
            models.Index(fields=["policy_type", "is_active"], name="rp_type_active_idx"),
        ]

    def __str__(self):
        return self.name


class RouterHealthSnapshot(models.Model):
    class HealthStatus(models.TextChoices):
        UP = "up", "Up"
        WARNING = "warning", "Warning"
        DOWN = "down", "Down"
        UNKNOWN = "unknown", "Unknown"

    class Source(models.TextChoices):
        SNMP = "snmp", "SNMP"
        SSH = "ssh", "SSH"
        API = "api", "RouterOS API"
        MANUAL = "manual", "Manual"
        SYSTEM = "system", "System"

    switch = models.ForeignKey(
        Switch,
        on_delete=models.CASCADE,
        related_name="router_health_snapshots",
    )
    collected_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=HealthStatus.choices, default=HealthStatus.UNKNOWN)
    source = models.CharField(max_length=30, choices=Source.choices, default=Source.SYSTEM)
    cpu_load = models.PositiveSmallIntegerField(null=True, blank=True)
    memory_free_mb = models.PositiveIntegerField(null=True, blank=True)
    uptime = models.CharField(max_length=100, blank=True)
    routeros_version = models.CharField(max_length=100, blank=True)
    public_ip = models.GenericIPAddressField(null=True, blank=True)
    tunnel_count = models.PositiveSmallIntegerField(default=0)
    active_tunnel_count = models.PositiveSmallIntegerField(default=0)
    raw_summary = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-collected_at"]
        indexes = [
            models.Index(fields=["switch", "-collected_at"], name="rhs_switch_collected_idx"),
            models.Index(fields=["status", "-collected_at"], name="rhs_status_collected_idx"),
            models.Index(fields=["source", "-collected_at"], name="rhs_source_collected_idx"),
        ]

    def __str__(self):
        return f"{self.switch.name} {self.status} {self.collected_at}"


class SSHJobTemplate(models.Model):
    class RiskLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    name = models.CharField(max_length=140, unique=True)
    action = models.CharField(max_length=60)
    value_template = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    risk_level = models.CharField(max_length=20, choices=RiskLevel.choices, default=RiskLevel.MEDIUM)
    requires_approval = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_by = models.CharField(max_length=150, blank=True)
    updated_by = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["risk_level", "name"]
        indexes = [
            models.Index(fields=["action", "is_active"], name="p77_job_action_active_idx"),
            models.Index(fields=["risk_level", "is_active"], name="p77_job_risk_active_idx"),
        ]

    def __str__(self):
        return self.name


class ConfigBackupSnapshot(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual Paste"
        SSH = "ssh", "SSH"
        SCHEDULED = "scheduled", "Scheduled"
        IMPORTED = "imported", "Imported"

    class ConfigType(models.TextChoices):
        RUNNING = "running", "Running Config"
        STARTUP = "startup", "Startup Config"
        EXPORT = "export", "Export"
        OTHER = "other", "Other"

    switch = models.ForeignKey(
        Switch,
        on_delete=models.CASCADE,
        related_name="config_backup_snapshots",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    actor_username = models.CharField(max_length=150, blank=True)
    command_source = models.CharField(max_length=30, choices=Source.choices, default=Source.MANUAL)
    config_type = models.CharField(max_length=30, choices=ConfigType.choices, default=ConfigType.RUNNING)
    command = models.CharField(max_length=150, default="show running-config", blank=True)
    content_hash = models.CharField(max_length=64, db_index=True)
    content = models.TextField()
    diff_text = models.TextField(blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["switch", "-created_at"], name="p77_cfg_switch_created_idx"),
            models.Index(fields=["config_type", "-created_at"], name="p77_cfg_type_created_idx"),
            models.Index(fields=["actor_username", "-created_at"], name="p77_cfg_actor_created_idx"),
        ]

    def __str__(self):
        return f"{self.switch.name} {self.config_type} {self.created_at}"
