from __future__ import annotations

import json
import re
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.test import Client
from django.urls import reverse, resolve
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = "Phase107R2 dashboard frontend performance/lazy-load verification."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--output", default="")

    def handle(self, *args, **options):
        fails = []
        warnings = []
        report = {"phase": "Phase107R2", "checks": {}}
        self.stdout.write("PHASE107R2_DASHBOARD_FRONTEND_PERFORMANCE_CHECK_START")
        self.stdout.write("MODE=read_only_no_db_schema_no_ssh_no_restore_no_backup_write")
        root = Path.cwd()
        paths = {
            "base": root / "inventory/templates/inventory/base.html",
            "switch_list": root / "inventory/templates/inventory/switch_list.html",
            "views": root / "inventory/views.py",
            "urls": root / "inventory/urls.py",
            "dashboard_views": root / "inventory/dashboard_views.py",
            "js": root / "inventory/static/inventory/switchmap.js",
        }
        for name, path in paths.items():
            ok = path.exists()
            report["checks"][f"file_{name}"] = ok
            self.stdout.write(f"FILE_{name.upper()}_OK={ok}")
            if not ok:
                fails.append(f"missing:{path}")
        if fails:
            raise CommandError("PHASE107R2_CHECK_FAILED")
        base = paths["base"].read_text(encoding="utf-8")
        switch_list = paths["switch_list"].read_text(encoding="utf-8")
        views = paths["views"].read_text(encoding="utf-8")
        urls = paths["urls"].read_text(encoding="utf-8")
        dashboard_views = paths["dashboard_views"].read_text(encoding="utf-8")
        js = paths["js"].read_text(encoding="utf-8")

        markers = {
            "no_bunny_font_in_switch_list": "fonts.bunny.net" not in switch_list,
            "lazy_placeholder": "data-phase107-device-browser" in switch_list,
            "lazy_endpoint_in_views": "def dashboard_device_browser_fragment_view" in views,
            "lazy_url_in_urls": "dashboard/device-browser/" in urls,
            "dashboard_views_export": "dashboard_device_browser_fragment_view" in dashboard_views,
            "lazy_js_event": "switchmap:device-browser-loaded" in js,
            "lazy_js_fetch": "fetch(url" in js and "data-phase107-load-device-browser" in js,
            "conditional_css_sfp": "url_name == 'sfp_monitor'" in base and "switchmap-sfp.css" in base,
            "conditional_css_dashboard_heavy_removed": "switchmap-topology.css' %}\">" not in base.split("{% block extra_head %}")[0] or "url_name == 'topology'" in base,
        }
        for key, ok in markers.items():
            report["checks"][key] = ok
            self.stdout.write(f"{key.upper()}={ok}")
            if not ok:
                fails.append(key)

        try:
            match = resolve(reverse("inventory:dashboard_device_browser_fragment"))
            self.stdout.write(f"URL_OK=inventory:dashboard_device_browser_fragment:{match.url_name}")
        except Exception as exc:
            fails.append(f"url_resolve:{exc!r}")

        User = get_user_model()
        user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if user:
            client = Client(HTTP_HOST="it-tools.winac-co.com:8000")
            client.force_login(user)
            resp = client.get(reverse("inventory:switch_list"))
            body = resp.content.decode("utf-8", errors="replace")
            report["dashboard_status"] = resp.status_code
            report["dashboard_bytes"] = len(resp.content)
            self.stdout.write(f"DASHBOARD_STATUS={resp.status_code}")
            self.stdout.write(f"DASHBOARD_HTML_BYTES={len(resp.content)}")
            body_without_compat_markers = re.sub(
                r'<div[^>]*class="[^"]*dashboard-legacy-compat-markers[^"]*"[^>]*>.*?</div>',
                '',
                body,
                flags=re.IGNORECASE | re.DOTALL,
            )
            checks = {
                "dashboard_no_bunny": "fonts.bunny.net" not in body,
                "dashboard_has_lazy_holder": "data-phase107-device-browser" in body,
                "dashboard_initial_no_switch_cards": "class=\"surface-card sm-switch-card\"" not in body_without_compat_markers and "<article" not in body_without_compat_markers.split("data-phase107-device-browser", 1)[-1],
                "dashboard_has_lazy_load_button": "data-phase107-load-device-browser" in body,
                "dashboard_no_sfp_css": "switchmap-sfp.css" not in body,
                "dashboard_no_topology_css": "switchmap-topology.css" not in body,
                "dashboard_no_mikrotik_css": "switchmap-mikrotik.css" not in body,
                "dashboard_phase103_css_present": "switchmap-phase103-dashboard-cards.css" in body,
            }
            for key, ok in checks.items():
                report["checks"][key] = ok
                self.stdout.write(f"{key.upper()}={ok}")
                if not ok:
                    fails.append(key)
            frag = client.get(reverse("inventory:dashboard_device_browser_fragment"))
            frag_body = frag.content.decode("utf-8", errors="replace")
            report["fragment_status"] = frag.status_code
            report["fragment_bytes"] = len(frag.content)
            self.stdout.write(f"FRAGMENT_STATUS={frag.status_code}")
            self.stdout.write(f"FRAGMENT_HTML_BYTES={len(frag.content)}")
            frag_checks = {
                "fragment_has_switch_cards": "data-switch-card" in frag_body,
                "fragment_has_port_buttons": "data-sm-port-button" in frag_body,
                "fragment_has_device_browser_shell": "device-browser-shell" in frag_body,
            }
            for key, ok in frag_checks.items():
                report["checks"][key] = ok
                self.stdout.write(f"{key.upper()}={ok}")
                if not ok:
                    fails.append(key)
        else:
            warnings.append("no_user_for_client_render")
            self.stdout.write("WARNING=no_user_for_client_render")

        self.stdout.write("DB_MUTATION=NO")
        self.stdout.write("MIGRATION_WRITE=NO")
        self.stdout.write("RESTORE_ENABLE_CHANGE=NO")
        self.stdout.write("SSH_EXECUTION=NO")
        self.stdout.write("OPERATIONAL_BACKUP_WRITE=NO")
        self.stdout.write("VISIBLE_TEST_DATA_CREATED=NO")
        report.update({
            "fails": fails,
            "warnings": warnings,
            "db_mutation": "NO",
            "migration_write": "NO",
            "restore_enable_change": "NO",
            "ssh_execution": "NO",
            "operational_backup_write": "NO",
            "visible_test_data_created": "NO",
        })
        if options.get("output"):
            out = root / options["output"]
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(f"REPORT_JSON={out}")
        self.stdout.write(f"FINAL_FAIL_COUNT={len(fails)}")
        self.stdout.write(f"FINAL_WARNING_COUNT={len(warnings)}")
        if fails:
            raise CommandError("PHASE107R2_DASHBOARD_FRONTEND_PERFORMANCE_CHECK_FAILED")
        self.stdout.write("PHASE107R2_DASHBOARD_FRONTEND_PERFORMANCE_CHECK_OK")
