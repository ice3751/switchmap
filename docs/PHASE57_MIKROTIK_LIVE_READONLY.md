# SwitchMap Phase 57 - MikroTik Live Read-Only Polling

## Scope

Adds manual live read-only SSH polling for MikroTik / RouterOS devices from MikroTik Center.

The phase adds:

- `/mikrotik/live-poll/` POST endpoint
- Manual credential prompt in MikroTik Center
- Read-only SSH collection of RouterOS health
- New `RouterHealthSnapshot` rows with source `SSH`
- JSON count for `live_ssh_polls`
- Smoke test for the UI, endpoint and snapshot creation

## Safety

No RouterOS configuration commands are executed.
No password is stored.
No RouterOS device setting is changed.

Read-only commands used:

```text
/system resource print
/system identity print
/interface print terse
/interface wireguard peers print terse
```

## Apply

```cmd
cd /d C:\SwitchMap
scripts\31_phase57_mikrotik_live_readonly.cmd
```

## Expected output

```text
SwitchMap phase 57 MikroTik live read-only smoke test: OK
SUMMARY 6 pass 0 fail
System check identified no issues
PHASE39_WAITRESS_RESTART_OK
```

## Rollback

Restore previous versions of:

- `inventory/mikrotik_views.py`
- `inventory/urls.py`
- `inventory/templates/inventory/mikrotik_center.html`
- `inventory/static/inventory/css/switchmap-mikrotik.css`
- `smoke_tests/manifest.json`

Then remove:

- `inventory/mikrotik_live.py`
- `smoke_tests/switchmap_57_mikrotik_live_readonly_smoke_test.py`
- `scripts/31_phase57_mikrotik_live_readonly.cmd`
- `docs/PHASE57_MIKROTIK_LIVE_READONLY.md`
- `README_PHASE57_APPLY.txt`

No migration is included in this phase.
