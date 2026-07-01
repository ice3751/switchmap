from __future__ import annotations
import os, sys
from pathlib import Path
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
from django.utils import timezone

def age(value):
    if not value:
        return "NEVER"
    s=max(0,int((timezone.now()-value).total_seconds()))
    if s<90: return f"{s}s"
    m=s//60
    if m<60: return f"{m}m"
    h=m//60
    if h<24: return f"{h}h{m%60}m"
    d=h//24
    return f"{d}d{h%24}h"

django.setup()
from inventory.models import Switch
print("PHASE72_1_SWITCH_ATTENTION")
for s in Switch.objects.filter(is_active=True).order_by("name"):
    name=(s.name or "")
    if any(x in name.lower() for x in ["karaj","rb2011","rb5009","phase","smoke"]):
        print(f"SWITCH={s.name}|ip={s.management_ip}|snmp={s.snmp_enabled}|ssh={s.ssh_enabled}|snmp_age={age(s.snmp_last_poll)}|discovery_age={age(s.discovery_last_poll)}|snmp_error={s.snmp_last_error or ''}|discovery_error={s.discovery_last_error or ''}")
print("PHASE72_1_SWITCH_ATTENTION_DONE")
