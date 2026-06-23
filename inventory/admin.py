from django.contrib import admin

from .models import AlarmNotification, CiscoSyslogEntry, Port, PortActionLog, PortDocumentationHistory, SfpMonitorSnapshot, Switch, SystemAuditLog


class PortInline(admin.TabularInline):
    model = Port
    extra = 0
    fields = (
        "interface_name",
        "display_order",
        "connected_device",
        "description",
        "port_mode",
        "access_vlan",
        "native_vlan",
        "voice_vlan",
        "trunk_vlans",
        "vlan",
        "status",
        "documentation_status",
        "owner",
        "room",
        "rack",
        "patch_panel",
        "patch_panel_port",
        "outlet",
        "cable_label",
    )
    readonly_fields = ("interface_name", "display_order")
    show_change_link = True


@admin.register(Switch)
class SwitchAdmin(admin.ModelAdmin):
    fieldsets = (
        (None, {
            "fields": (
                "name",
                "management_ip",
                "model",
                "vendor",
                "device_family",
                "device_role",
                "site",
                "location",
                "topology_position",
                "winbox_port",
                "needs_review",
                "port_count",
                "notes",
                "is_active",
            )
        }),
        ("SNMP Read Only", {
            "fields": (
                "snmp_enabled",
                "snmp_community",
                "snmp_port",
                "snmp_timeout",
                "snmp_last_poll",
                "snmp_last_error",
                "discovery_last_poll",
                "discovery_last_error",
            )
        }),
        ("SSH Helper", {
            "fields": (
                "ssh_enabled",
                "ssh_username",
                "ssh_port",
            )
        }),
    )
    readonly_fields = (
        "snmp_last_poll",
        "snmp_last_error",
        "discovery_last_poll",
        "discovery_last_error",
    )
    list_display = (
        "name",
        "management_ip",
        "model",
        "vendor",
        "device_family",
        "device_role",
        "site",
        "location",
        "topology_position",
        "winbox_port",
        "needs_review",
        "port_count",
        "snmp_enabled",
        "ssh_enabled",
        "is_active",
    )
    search_fields = (
        "name",
        "management_ip",
        "model",
        "vendor",
        "device_family",
        "device_role",
        "site",
        "location",
    )
    list_filter = (
        "vendor",
        "device_family",
        "device_role",
        "site",
        "model",
        "is_active",
        "needs_review",
        "location",
    )
    inlines = (
        PortInline,
    )


@admin.register(Port)
class PortAdmin(admin.ModelAdmin):
    list_display = (
        "switch",
        "interface_name",
        "display_order",
        "connected_device",
        "port_mode",
        "access_vlan",
        "native_vlan",
        "voice_vlan",
        "trunk_vlans",
        "vlan",
        "status",
        "snmp_oper_status",
        "neighbor_device",
        "mac_count",
        "documentation_status",
        "owner",
        "room",
        "rack",
        "asset_tag",
        "updated_at",
    )
    list_editable = (
        "connected_device",
        "port_mode",
        "access_vlan",
        "native_vlan",
        "voice_vlan",
        "trunk_vlans",
        "vlan",
        "status",
    )
    search_fields = (
        "switch__name",
        "interface_name",
        "connected_device",
        "description",
        "owner",
        "ip_address",
        "mac_address",
        "snmp_raw_name",
        "snmp_alias",
        "snmp_oper_status",
        "neighbor_device",
        "neighbor_port",
        "mac_addresses",
        "room",
        "rack",
        "rack_unit",
        "patch_panel",
        "patch_panel_port",
        "outlet",
        "cable_label",
        "cable_type",
        "cable_length",
        "asset_tag",
        "documentation_status",
        "notes",
    )
    list_filter = (
        "switch",
        "status",
        "port_mode",
        "access_vlan",
        "voice_vlan",
        "vlan",
        "poe_enabled",
        "poe_admin_status",
        "poe_detection_status",
        "room",
        "rack",
        "documentation_status",
    )
    autocomplete_fields = (
        "switch",
    )
    ordering = (
        "switch",
        "display_order",
    )



@admin.register(PortDocumentationHistory)
class PortDocumentationHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "switch",
        "interface_name",
        "changed_fields",
        "actor_username",
        "actor_role",
        "client_ip",
    )
    search_fields = (
        "switch__name",
        "port__interface_name",
        "interface_name",
        "changed_fields",
        "actor_username",
        "actor_role",
        "before_data",
        "after_data",
        "note",
    )
    list_filter = (
        "switch",
        "actor_username",
        "actor_role",
    )
    readonly_fields = (
        "created_at",
        "port",
        "switch",
        "interface_name",
        "changed_fields",
        "before_data",
        "after_data",
        "actor_username",
        "actor_role",
        "client_ip",
        "request_path",
        "note",
    )


@admin.register(PortActionLog)
class PortActionLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "switch",
        "port",
        "action",
        "value",
        "ssh_username",
        "actor_username",
        "actor_role",
        "client_ip",
        "success",
    )
    search_fields = (
        "switch__name",
        "port__interface_name",
        "action",
        "value",
        "ssh_username",
        "actor_username",
        "actor_role",
        "client_ip",
        "request_path",
        "action_label",
        "message",
        "commands",
    )
    list_filter = (
        "success",
        "action",
        "switch",
        "actor_username",
        "actor_role",
        "client_ip",
    )
    readonly_fields = (
        "created_at",
        "switch",
        "port",
        "action",
        "value",
        "ssh_username",
        "actor_username",
        "actor_role",
        "client_ip",
        "request_path",
        "action_label",
        "success",
        "message",
        "commands",
    )

@admin.register(CiscoSyslogEntry)
class CiscoSyslogEntryAdmin(admin.ModelAdmin):
    list_display = (
        "received_at",
        "switch",
        "source_ip",
        "severity",
        "severity_name",
        "facility",
        "mnemonic",
        "category",
        "interface_name",
        "is_parsed",
    )
    search_fields = (
        "switch__name",
        "source_ip",
        "facility",
        "mnemonic",
        "category",
        "interface_name",
        "message",
        "raw_line",
    )
    list_filter = (
        "severity",
        "category",
        "facility",
        "switch",
        "is_parsed",
    )
    readonly_fields = (
        "received_at",
        "switch",
        "event_time_text",
        "source_ip",
        "facility",
        "severity",
        "severity_name",
        "mnemonic",
        "category",
        "interface_name",
        "message",
        "raw_line",
        "is_parsed",
    )



@admin.register(SfpMonitorSnapshot)
class SfpMonitorSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "poll_time",
        "switch",
        "interface_name",
        "link_status",
        "err_disabled",
        "fcs_delta",
        "input_error_delta",
        "output_error_delta",
        "rx_power_dbm",
        "tx_power_dbm",
        "temperature_c",
        "health_state",
    )
    search_fields = (
        "switch__name",
        "interface_name",
        "link_status",
        "media_type",
        "health_note",
    )
    list_filter = (
        "health_state",
        "err_disabled",
        "switch",
    )
    readonly_fields = tuple(field.name for field in SfpMonitorSnapshot._meta.fields)


@admin.register(AlarmNotification)
class AlarmNotificationAdmin(admin.ModelAdmin):
    list_display = (
        "last_seen",
        "severity",
        "status",
        "category",
        "switch",
        "port",
        "title",
        "occurrences",
        "acknowledged_by",
    )
    search_fields = (
        "fingerprint",
        "source",
        "title",
        "message",
        "details",
        "switch__name",
        "switch__management_ip",
        "port__interface_name",
        "acknowledged_by",
    )
    list_filter = (
        "status",
        "severity",
        "category",
        "switch",
    )
    readonly_fields = (
        "fingerprint",
        "source",
        "category",
        "severity",
        "status",
        "title",
        "message",
        "details",
        "first_seen",
        "last_seen",
        "resolved_at",
        "acknowledged_at",
        "acknowledged_by",
        "occurrences",
        "switch",
        "port",
    )



@admin.register(SystemAuditLog)
class SystemAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "category",
        "action",
        "actor_username",
        "actor_role",
        "target_username",
        "client_ip",
    )
    search_fields = (
        "category",
        "action",
        "actor_username",
        "actor_role",
        "target_username",
        "client_ip",
        "request_path",
        "message",
    )
    list_filter = (
        "category",
        "action",
        "actor_role",
    )
    readonly_fields = tuple(field.name for field in SystemAuditLog._meta.fields)
