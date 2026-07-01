from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.models import RouterHealthSnapshot, RouterTunnel, RoutingPolicy, Site, Switch, WanLink


SITE_ROWS = [
    {"code": "qazvin", "name": "Qazvin HQ", "kind": Site.Kind.HQ, "description": "Main HQ / core network."},
    {"code": "tehran_iranmall", "name": "Tehran / Iranmall", "kind": Site.Kind.REMOTE, "description": "Remote office connected to HQ."},
    {"code": "ali_home", "name": "Ali Home", "kind": Site.Kind.HOME, "description": "Home/remote router site."},
    {"code": "karaj", "name": "Karaj", "kind": Site.Kind.REMOTE, "description": "Karaj remote router site."},
    {"code": "germany_vps", "name": "Germany VPS", "kind": Site.Kind.CLOUD, "description": "Cloud/VPS RouterOS endpoint."},
    {"code": "qazvin_wireless", "name": "Qazvin Wireless", "kind": Site.Kind.WIRELESS, "description": "CAP / AP management scope."},
]


def switch_by_name_or_ip(name, ip=None):
    if ip:
        item = Switch.objects.filter(management_ip=ip).first()
        if item:
            return item
    return Switch.objects.filter(name__iexact=name).first()


def upsert(model, lookup, defaults, dry_run=False):
    obj = model.objects.filter(**lookup).first()
    if obj:
        changed = []
        for key, value in defaults.items():
            if getattr(obj, key) != value:
                setattr(obj, key, value)
                changed.append(key)
        if changed and not dry_run:
            obj.save(update_fields=changed)
        return obj, False, changed
    if dry_run:
        return None, True, list(defaults.keys())
    return model.objects.create(**lookup, **defaults), True, list(defaults.keys())


class Command(BaseCommand):
    help = "Seed read-only MikroTik data model foundation: sites, WAN links, tunnels, routing policies and baseline health snapshots."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--with-health", action="store_true", help="Create lightweight system health snapshots from current SwitchMap data.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        with_health = options["with_health"]
        created = {"sites": 0, "wan": 0, "tunnels": 0, "policies": 0, "health": 0}
        updated = {"sites": 0, "wan": 0, "tunnels": 0, "policies": 0}

        sites = {}
        for row in SITE_ROWS:
            obj, was_created, changed = upsert(
                Site,
                {"code": row["code"]},
                {"name": row["name"], "kind": row["kind"], "description": row["description"], "is_active": True},
                dry_run=dry_run,
            )
            sites[row["code"]] = obj
            created["sites"] += int(was_created)
            updated["sites"] += int((not was_created) and bool(changed))

        rb5009 = switch_by_name_or_ip("RB5009", "192.168.0.234")
        rb2011 = switch_by_name_or_ip("RB2011-Iranmall", "172.20.20.1")
        ali_home = switch_by_name_or_ip("AliHome", "192.168.2.1")
        ax3 = switch_by_name_or_ip("AX3-Karaj", "192.168.102.1")
        vps = switch_by_name_or_ip("VPS-Germany", "213.183.63.107")
        hexs = switch_by_name_or_ip("Hex-S", "192.168.0.253")

        wan_rows = [
            {"name": "RB5009 - Starlink", "switch": rb5009, "site": sites.get("qazvin"), "link_type": WanLink.LinkType.STARLINK, "provider": "Starlink", "interface_name": "ether4-INTERNET", "purpose": "Foreign / international traffic", "is_primary": True, "notes": "Known HQ foreign internet path."},
            {"name": "RB5009 - Rasana/Pishtaz", "switch": rb5009, "site": sites.get("qazvin"), "link_type": WanLink.LinkType.FIBER, "provider": "Rasana/Pishtaz", "interface_name": "Iran ISP", "purpose": "Iran/local traffic", "is_primary": False, "notes": "Known Iran-only path."},
            {"name": "Hex-S - Local Transit", "switch": hexs, "site": sites.get("qazvin"), "link_type": WanLink.LinkType.LOCAL_TRANSIT, "provider": "LAN Transit", "interface_name": "LAN/SFP", "purpose": "Local internet handoff / transit", "is_primary": False, "notes": "Treat as transit, not switch-only topology."},
            {"name": "AliHome - Home ISP", "switch": ali_home, "site": sites.get("ali_home"), "link_type": WanLink.LinkType.FIBER, "provider": "Home ISP", "interface_name": "WAN", "purpose": "Local Iran traffic + VPN backhaul", "is_primary": True, "notes": "Credentials are not stored."},
            {"name": "AX3-Karaj - Local WAN", "switch": ax3, "site": sites.get("karaj"), "link_type": WanLink.LinkType.SIM, "provider": "Karaj WAN", "interface_name": "WAN", "purpose": "Local Iran traffic + WireGuard backhaul", "is_primary": True, "notes": "May be fiber/SIM depending on current physical uplink."},
            {"name": "VPS-Germany - Public Internet", "switch": vps, "site": sites.get("germany_vps"), "link_type": WanLink.LinkType.VPS, "provider": "Germany VPS", "interface_name": "public", "purpose": "External RouterOS endpoint", "is_primary": True, "notes": "Verify live state before operational decisions."},
        ]
        for row in wan_rows:
            name = row.pop("name")
            if not row.get("switch") and not row.get("site"):
                continue
            obj, was_created, changed = upsert(WanLink, {"name": name}, {**row, "is_active": True}, dry_run=dry_run)
            created["wan"] += int(was_created)
            updated["wan"] += int((not was_created) and bool(changed))

        tunnel_rows = [
            {"name": "HQ to Tehran WireGuard", "tunnel_type": RouterTunnel.TunnelType.WIREGUARD, "source_switch": rb5009, "destination_switch": rb2011, "source_site": sites.get("qazvin"), "destination_site": sites.get("tehran_iranmall"), "local_tunnel_ip": "172.16.11.1", "remote_tunnel_ip": "172.16.11.2", "routed_networks": "192.168.0.0/24 ↔ 192.168.101.0/24", "failover_priority": 1, "status": RouterTunnel.Status.UNKNOWN, "confidence": RouterTunnel.Confidence.DOCUMENTED, "notes": "Primary Tehran/Qazvin route."},
            {"name": "HQ to Tehran EoIP Backup", "tunnel_type": RouterTunnel.TunnelType.EOIP, "source_switch": rb5009, "destination_switch": rb2011, "source_site": sites.get("qazvin"), "destination_site": sites.get("tehran_iranmall"), "local_tunnel_ip": "172.20.20.2", "remote_tunnel_ip": "172.20.20.1", "routed_networks": "192.168.0.0/24 ↔ 192.168.101.0/24", "failover_priority": 2, "status": RouterTunnel.Status.UNKNOWN, "confidence": RouterTunnel.Confidence.DOCUMENTED, "notes": "Documented backup path. GRE is not the primary backup baseline."},
            {"name": "HQ to AliHome L2TP", "tunnel_type": RouterTunnel.TunnelType.L2TP_IPSEC, "source_switch": rb5009, "destination_switch": ali_home, "source_site": sites.get("qazvin"), "destination_site": sites.get("ali_home"), "local_tunnel_ip": "10.255.20.1", "remote_tunnel_ip": "10.255.20.2", "routed_networks": "HQ ↔ 192.168.2.0/24", "failover_priority": 1, "status": RouterTunnel.Status.UNKNOWN, "confidence": RouterTunnel.Confidence.DOCUMENTED, "notes": "AliHome L2TP/IPsec relationship."},
            {"name": "HQ to Karaj WireGuard", "tunnel_type": RouterTunnel.TunnelType.WIREGUARD, "source_switch": rb5009, "destination_switch": ax3, "source_site": sites.get("qazvin"), "destination_site": sites.get("karaj"), "local_tunnel_ip": "10.255.30.1", "remote_tunnel_ip": "10.255.30.2", "routed_networks": "HQ ↔ 192.168.102.0/24", "failover_priority": 1, "status": RouterTunnel.Status.UNKNOWN, "confidence": RouterTunnel.Confidence.DOCUMENTED, "notes": "Karaj WireGuard spoke."},
            {"name": "HQ to Germany VPS", "tunnel_type": RouterTunnel.TunnelType.VPN_ENDPOINT, "source_switch": rb5009, "destination_switch": vps, "source_site": sites.get("qazvin"), "destination_site": sites.get("germany_vps"), "local_tunnel_ip": None, "remote_tunnel_ip": "213.183.63.107", "routed_networks": "VPN / external endpoint", "failover_priority": 10, "status": RouterTunnel.Status.UNKNOWN, "confidence": RouterTunnel.Confidence.INFERRED, "notes": "Endpoint is known; live tunnel details need future poll."},
            {"name": "HQ to Hex-S Local Transit", "tunnel_type": RouterTunnel.TunnelType.LOCAL_TRANSIT, "source_switch": rb5009, "destination_switch": hexs, "source_site": sites.get("qazvin"), "destination_site": sites.get("qazvin"), "local_tunnel_ip": "192.168.0.234", "remote_tunnel_ip": "192.168.0.253", "routed_networks": "Local LAN / transit", "failover_priority": 1, "status": RouterTunnel.Status.UNKNOWN, "confidence": RouterTunnel.Confidence.DOCUMENTED, "notes": "Local transit relationship, not a VPN tunnel."},
        ]
        for row in tunnel_rows:
            name = row.pop("name")
            if not row.get("source_switch") and not row.get("destination_switch"):
                continue
            obj, was_created, changed = upsert(RouterTunnel, {"name": name}, {**row, "is_active": True}, dry_run=dry_run)
            created["tunnels"] += int(was_created)
            updated["tunnels"] += int((not was_created) and bool(changed))

        policy_rows = [
            {"name": "HQ Iran traffic", "switch": rb5009, "site": sites.get("qazvin"), "policy_type": RoutingPolicy.PolicyType.IRAN, "source_zone": "HQ LAN", "destination_zone": "Iran destinations", "preferred_path": "Rasana/Pishtaz", "backup_path": "-", "routing_table": "Iran", "address_list": "Iran/Internal", "description": "Domestic traffic should use Iran ISP path.", "confidence": RoutingPolicy.Confidence.DOCUMENTED},
            {"name": "HQ foreign traffic", "switch": rb5009, "site": sites.get("qazvin"), "policy_type": RoutingPolicy.PolicyType.FOREIGN, "source_zone": "HQ LAN", "destination_zone": "Foreign destinations", "preferred_path": "Starlink", "backup_path": "-", "routing_table": "Starlink/Foreign", "address_list": "Foreign/Bypass", "description": "International traffic should use Starlink path.", "confidence": RoutingPolicy.Confidence.DOCUMENTED},
            {"name": "Tehran site-to-site", "switch": rb2011, "site": sites.get("tehran_iranmall"), "policy_type": RoutingPolicy.PolicyType.SITE_TO_SITE, "source_zone": "192.168.101.0/24", "destination_zone": "192.168.0.0/24", "preferred_path": "WireGuard", "backup_path": "EoIP", "routing_table": "main", "address_list": "-", "description": "WireGuard primary, EoIP documented backup.", "confidence": RoutingPolicy.Confidence.DOCUMENTED},
            {"name": "AliHome split path", "switch": ali_home, "site": sites.get("ali_home"), "policy_type": RoutingPolicy.PolicyType.SITE_TO_SITE, "source_zone": "192.168.2.0/24", "destination_zone": "HQ/Foreign", "preferred_path": "L2TP/IPsec to HQ", "backup_path": "Local WAN", "routing_table": "main", "address_list": "Iran/Internal", "description": "Local Iran path remains local; foreign/HQ path can use tunnel.", "confidence": RoutingPolicy.Confidence.DOCUMENTED},
            {"name": "Karaj split path", "switch": ax3, "site": sites.get("karaj"), "policy_type": RoutingPolicy.PolicyType.SITE_TO_SITE, "source_zone": "192.168.102.0/24", "destination_zone": "HQ/Foreign", "preferred_path": "WireGuard to HQ", "backup_path": "Local WAN", "routing_table": "main", "address_list": "Iran/Internal", "description": "Iran traffic local WAN; foreign traffic via HQ/Starlink.", "confidence": RoutingPolicy.Confidence.DOCUMENTED},
            {"name": "Wireless management", "switch": None, "site": sites.get("qazvin_wireless"), "policy_type": RoutingPolicy.PolicyType.MANAGEMENT, "source_zone": "CAP/AP", "destination_zone": "Management VLAN", "preferred_path": "Local management", "backup_path": "-", "routing_table": "main", "address_list": "-", "description": "APs should be monitored as wireless endpoints, not routing hubs.", "confidence": RoutingPolicy.Confidence.INFERRED},
        ]
        for row in policy_rows:
            name = row.pop("name")
            obj, was_created, changed = upsert(RoutingPolicy, {"name": name}, {**row, "is_active": True}, dry_run=dry_run)
            created["policies"] += int(was_created)
            updated["policies"] += int((not was_created) and bool(changed))

        if with_health:
            now = timezone.now()
            switches = Switch.objects.filter(vendor=Switch.Vendor.MIKROTIK, is_active=True).order_by("name")
            for switch in switches:
                if dry_run:
                    created["health"] += 1
                    continue
                latest = switch.router_health_snapshots.order_by("-collected_at").first()
                if latest and (now - latest.collected_at).total_seconds() < 300:
                    continue
                status = RouterHealthSnapshot.HealthStatus.UNKNOWN
                if switch.snmp_last_poll and not switch.snmp_last_error:
                    status = RouterHealthSnapshot.HealthStatus.UP
                elif switch.snmp_last_error or switch.discovery_last_error:
                    status = RouterHealthSnapshot.HealthStatus.WARNING
                out_count = switch.outbound_router_tunnels.filter(is_active=True).count()
                in_count = switch.inbound_router_tunnels.filter(is_active=True).count()
                RouterHealthSnapshot.objects.create(
                    switch=switch,
                    status=status,
                    source=RouterHealthSnapshot.Source.SYSTEM,
                    tunnel_count=out_count + in_count,
                    active_tunnel_count=0,
                    raw_summary="Baseline from existing SwitchMap metadata; not live RouterOS poll.",
                )
                created["health"] += 1

        suffix = "DRY_RUN" if dry_run else "OK"
        self.stdout.write(
            f"MIKROTIK_FOUNDATION_SEED_{suffix} "
            f"sites_created={created['sites']} sites_updated={updated['sites']} "
            f"wan_created={created['wan']} wan_updated={updated['wan']} "
            f"tunnels_created={created['tunnels']} tunnels_updated={updated['tunnels']} "
            f"policies_created={created['policies']} policies_updated={updated['policies']} "
            f"health_created={created['health']}"
        )
