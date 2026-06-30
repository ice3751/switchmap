# SwitchMap Phase 58.1 - Smoke Test Django Setup Fix

Fixes the phase 58 smoke test import order so `django.setup()` runs before importing Django ORM models such as `Group`.

No UI, database, migration, RouterOS, SSH, SNMP, or production setting change is included.
