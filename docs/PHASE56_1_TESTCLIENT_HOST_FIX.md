# SwitchMap Phase 56.1 - Test Client Host Fix

Fixes the phase 56 smoke test so Django test client uses `127.0.0.1` instead of the default `testserver` host.

Scope:
- Smoke test only
- No database changes
- No migration changes
- No application behavior changes
- No RouterOS / SSH / SNMP changes
