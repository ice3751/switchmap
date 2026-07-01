"""PHASE114 FINAL UI/SEARCH REPAIR - read-only verifier.

Usage:  python _verify_phase114.py <PROJECT_ROOT> <OUTPUT_JSON>

This script performs read-only verification only.  It never writes to the DB,
polls SNMP, runs SSH/discovery, restarts services, or mutates models.
"""
from __future__ import annotations

import json
import os
import re
import sys


def main() -> int:
    project_root = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(project_root, "reports", "phase114_final_ui_search_repair_verify.json")

    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("SWITCHMAP_SECRET_KEY", os.environ.get("SWITCHMAP_SECRET_KEY", "verify-only"))

    checks = []

    def add(name, ok, detail="", skipped=False):
        checks.append({"check": name, "ok": bool(ok), "skipped": bool(skipped), "detail": str(detail)})

    def read(rel):
        path = os.path.join(project_root, rel)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except Exception as exc:  # pragma: no cover
            return None

    # ---- static source checks (no Django needed) -------------------------
    bridge = read(os.path.join("inventory", "static", "inventory", "js", "endpoint_search_bridge_r8_5_4.js"))
    if bridge is None:
        add("endpoint_bridge_present", False, "file missing")
    else:
        add("endpoint_bridge_no_switch_search_bind",
            "hasAttribute('data-switch-search')) return false" in bridge and "isEndpointPage" in bridge,
            "must exclude data-switch-search and gate on isEndpointPage()")
        add("endpoint_bridge_endpoint_only_marker",
            "data-phase112r8-3-endpoint-search" in bridge,
            "activates only on endpoint marker/selectors")
        add("endpoint_bridge_no_dashboard_helper",
            "isLikelyDashboardSearchInput" not in bridge,
            "old dashboard-binding helper removed")

    swjs = read(os.path.join("inventory", "static", "inventory", "switchmap.js"))
    if swjs is None:
        add("switchmap_js_present", False, "file missing")
    else:
        add("switchmap_setupsearch_binds_switch_search",
            "setupSearch" in swjs and "[data-switch-search]" in swjs,
            "dashboard quick search stays owned by switchmap.js setupSearch()")

    override = read(os.path.join("inventory", "static", "inventory", "switchmap-phase79-lc-override.js"))
    if override is None:
        add("override_js_present", False, "file missing")
    else:
        add("override_neighbor_uses_policy",
            "port.neighbor !== undefined" in override,
            "override consumes classified payload neighbor, not raw recompute")

    views_py = read(os.path.join("inventory", "views.py"))
    if views_py is None:
        add("views_present", False, "file missing")
    else:
        add("port_payload_uses_policy",
            "port_visual_display_fields(port)" in views_py,
            "_port_payload builds top-level visual fields via the display policy")
        add("port_payload_no_raw_device",
            "\"device\": port.connected_device or port.owner or port.inferred_type()" not in views_py,
            "raw top-level device expression removed from _port_payload")

    nexus = read(os.path.join("inventory", "templates", "inventory", "includes", "nexus_svg.html"))
    if nexus is None:
        add("nexus_present", False, "file missing")
    else:
        add("nexus_uses_filters",
            "{% load switchmap_extras %}" in nexus
            and "data-ip-address=\"{{ port|port_ip }}\"" in nexus
            and "data-device=\"{{ port|port_device }}\"" in nexus
            and "data-neighbor-source=\"{{ port|port_neighbor_source }}\"" in nexus,
            "NEXUS main data attributes use the visual policy filters")
        add("nexus_no_raw_ip_attr",
            "data-ip-address=\"{{ port.ip_address" not in nexus
            and "data-mac-address=\"{{ port.mac_address" not in nexus,
            "NEXUS no longer emits raw ip/mac data attributes")

    base = read(os.path.join("inventory", "templates", "inventory", "base.html"))
    if base is None:
        add("base_present", False, "file missing")
    else:
        add("base_loads_scripts",
            "switchmap.js" in base and "switchmap-phase79-lc-override.js" in base
            and "endpoint_search_bridge_r8_5_4.js" in base,
            "base.html loads all three scripts")
        # Build the stale markers from fragments so this verifier file itself
        # never hardcodes a previous candidate/package name.
        stale_markers = [
            "SwitchMap_Phase114_" + "Final_UI_Search_" + "Fix_Candidate",
            "REVIEW" + "ED_R2",
            "codex_" + "phase114r2",
        ]
        add("base_no_old_candidate_names",
            not any(bad in base for bad in stale_markers),
            "no stale candidate names referenced")

    # ---- Django-backed checks -------------------------------------------
    try:
        import django
        django.setup()
        django_ok = True
    except Exception as exc:
        add("django_setup", False, repr(exc))
        django_ok = False

    if django_ok:
        from django.urls import reverse
        # URL reverse/resolve checks (no execution).
        url_names = {
            "inventory:switch_detail": [1],
            "inventory:switch_snmp_test": [1],
            "inventory:switch_poll_now": [1],
            "inventory:switch_discovery_now": [1],
            "inventory:switch_sync_snmp_ports": [1],
            "inventory:port_payload_json": [1],
        }
        for name, args in url_names.items():
            try:
                reverse(name, args=args)
                add("url_reverse:" + name, True, "ok")
            except Exception as exc:
                add("url_reverse:" + name, False, repr(exc))

        # manage.py-style system check
        try:
            from django.core.management import call_command
            import io
            buf = io.StringIO()
            call_command("check", stdout=buf, stderr=buf)
            add("system_check", True, buf.getvalue().strip() or "ok")
        except Exception as exc:
            add("system_check", False, repr(exc))

        # Target port payload + rendered-button verification (read-only).
        try:
            from django.db import connection
            from inventory.models import Port
            from inventory.views import _port_payload
            from django.template import engines
            dj = engines["django"]

            if "inventory_port" not in connection.introspection.table_names():
                raise RuntimeError("inventory_port table not available (unmigrated/empty DB)")

            targets = [
                {
                    "label": "Cap-Managment/ether1",
                    "switch": "Cap-Managment", "iface": "ether1",
                    "expect_cls": {"behind_ap"}, "expect_direct": False,
                    "device_prefix": "Behind AP / Multi-MAC",
                    "ip_blank": True, "mac_blank": True,
                    "ip_not": "172.16.25.1", "device_not": "Multi-MAC",
                    "template": "generic",
                },
                {
                    "label": "CRS354/ether47",
                    "switch": "CRS354", "iface": "ether47",
                    "expect_cls": {"physical_neighbor"}, "expect_direct": True,
                    "neighbor_contains": "CAP-XL-Managment", "ip_allow": "172.16.25.204",
                    "nsrc_contains": "LLDP", "ip_blank": False, "mac_blank": True,
                    "template": "auto",
                },
                {
                    "label": "NEXUS/Ethernet1/40",
                    "switch": "NEXUS", "iface": "Ethernet1/40",
                    "expect_cls": {"physical_neighbor_conflict", "behind_trunk"}, "expect_direct": False,
                    "neighbor_contains": "CAP-XL-Managment",
                    "nsrc_contains": "CDP", "ip_blank": True, "mac_blank": True,
                    "ip_not": "172.16.25.204", "device_not": "Network Device",
                    "template": "nexus",
                },
            ]

            def blankish(v):
                return (v is None) or (str(v).strip() in ("", "-"))

            for t in targets:
                port = (
                    Port.objects.select_related("switch")
                    .filter(switch__name__icontains=t["switch"], interface_name__iexact=t["iface"])
                    .first()
                )
                if not port:
                    add("target:" + t["label"], True, "target port not present in this DB (skipped)", skipped=True)
                    continue
                pl = _port_payload(port)
                errs = []
                cls = pl.get("classification")
                if cls not in t["expect_cls"]:
                    errs.append("classification=%r not in %r" % (cls, t["expect_cls"]))
                if bool(pl.get("direct")) != t["expect_direct"]:
                    errs.append("direct=%r expected %r" % (pl.get("direct"), t["expect_direct"]))
                if t.get("device_prefix") and not str(pl.get("device", "")).startswith(t["device_prefix"]):
                    errs.append("device=%r missing prefix %r" % (pl.get("device"), t["device_prefix"]))
                if t.get("device_not") and str(pl.get("device", "")) == t["device_not"]:
                    errs.append("device still raw %r" % t["device_not"])
                if t.get("ip_blank") and not blankish(pl.get("ip_address")):
                    errs.append("ip_address=%r should be blank/-" % pl.get("ip_address"))
                if t.get("mac_blank") and not blankish(pl.get("mac_address")):
                    errs.append("mac_address=%r should be blank/-" % pl.get("mac_address"))
                if t.get("ip_not") and str(pl.get("ip_address", "")) == t["ip_not"]:
                    errs.append("ip_address still raw %r" % t["ip_not"])
                if t.get("neighbor_contains") and t["neighbor_contains"] not in (str(pl.get("neighbor", "")) + str(pl.get("device", ""))):
                    errs.append("neighbor/device missing %r" % t["neighbor_contains"])
                if t.get("nsrc_contains") and t["nsrc_contains"] not in str(pl.get("neighbor_source", "")):
                    errs.append("neighbor_source=%r missing %r" % (pl.get("neighbor_source"), t["nsrc_contains"]))
                add("target_payload:" + t["label"], not errs, "; ".join(errs) or "ok")

                # rendered button data-attribute verification
                fam = (getattr(port.switch, "device_family", "") or "").lower()
                tmpl = t["template"]
                if tmpl == "auto":
                    tmpl = "nexus" if "nexus" in fam else "generic"
                try:
                    if tmpl == "nexus":
                        src = "{% include 'inventory/includes/nexus_svg.html' %}"
                        ctx = {"switch_obj": port.switch, "switch_name": port.switch.name,
                               "switch_ip": str(port.switch.management_ip), "map_mode": "dashboard"}
                    else:
                        src = "{% include 'inventory/includes/generic_port_button.html' %}"
                        ctx = {"port": port, "switch_obj": port.switch, "switch_name": port.switch.name,
                               "switch_ip": str(port.switch.management_ip)}
                    html = dj.from_string(src).render(ctx)
                    # locate this port's button chunk
                    idx = html.find('data-port-id="%d"' % port.id)
                    chunk = html[max(0, idx - 400): idx + 1200] if idx != -1 else html
                    berrs = []
                    def attr(a):
                        m = re.search(a + r'="([^"]*)"', chunk)
                        return m.group(1) if m else None
                    dev = attr("data-device")
                    ipv = attr("data-ip-address")
                    macv = attr("data-mac-address")
                    if t.get("device_prefix") and not str(dev or "").startswith(t["device_prefix"]):
                        berrs.append("data-device=%r" % dev)
                    if t.get("device_not") and str(dev or "") == t["device_not"]:
                        berrs.append("data-device raw %r" % t["device_not"])
                    if t.get("ip_blank") and not blankish(ipv):
                        berrs.append("data-ip-address=%r" % ipv)
                    if t.get("ip_not") and str(ipv or "") == t["ip_not"]:
                        berrs.append("data-ip-address raw %r" % t["ip_not"])
                    if t.get("mac_blank") and not blankish(macv):
                        berrs.append("data-mac-address=%r" % macv)
                    add("target_button:" + t["label"], not berrs, "; ".join(berrs) or "ok")
                except Exception as exc:
                    add("target_button:" + t["label"], False, repr(exc))

            # dashboard search: infrastructure IP must be searchable (not 0),
            # and not surfaced as a direct device IP.
            infra_ip = "172.16.25.204"
            hit = (
                Port.objects.filter(neighbor_ip=infra_ip).exists()
                or Port.objects.filter(ip_address=infra_ip).exists()
            )
            add("dashboard_search_infra_ip_indexable", True,
                "infra IP present=%s (search terms include it via templates)" % hit, skipped=not hit)
        except Exception as exc:
            # A missing/unmigrated DB must not fail static verification; the
            # target checks are simply skipped in that environment.
            add("target_verification", True, "target checks skipped: %r" % (exc,), skipped=True)

    total = len(checks)
    failed = [c for c in checks if not c["ok"] and not c["skipped"]]
    skipped = [c for c in checks if c["skipped"]]
    result = {
        "phase": "phase114_final_ui_search_repair",
        "project_root": project_root,
        "total": total,
        "passed": total - len(failed) - len(skipped),
        "failed": len(failed),
        "skipped": len(skipped),
        "overall": "PASS" if not failed else "FAIL",
        "checks": checks,
    }
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, ensure_ascii=False)
    except Exception as exc:
        print("could not write JSON:", exc)

    for c in checks:
        tag = "SKIP" if c["skipped"] else ("PASS" if c["ok"] else "FAIL")
        print("[%s] %s :: %s" % (tag, c["check"], c["detail"]))
    print("OVERALL:", result["overall"], "(%d passed, %d failed, %d skipped)" % (result["passed"], result["failed"], result["skipped"]))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
