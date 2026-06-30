# SwitchMap Phase 56.2 - Test Device Menu Filter Fix

## Scope

Fixes a false-positive Phase 56 smoke failure where the temporary smoke MikroTik device was correctly filtered from the MikroTik Center payload but still appeared in the global top navigation switch menu rendered by `base.html`.

## Changed

- `inventory/context_processors.py`
- `scripts/30_phase56_2_test_device_menu_filter_fix.cmd`
- `docs/PHASE56_2_TEST_DEVICE_MENU_FILTER_FIX.md`

## Not changed

- No models
- No migrations
- No database data
- No RouterOS / SSH / SNMP logic
- No MikroTik operational behavior

## Validation

```cmd
cd /d C:\SwitchMap
scripts\30_phase56_2_test_device_menu_filter_fix.cmd
```

Expected:

```text
SwitchMap phase 56 MikroTik data quality smoke test: OK
SUMMARY 5 pass 0 fail
System check identified no issues
PHASE39_WAITRESS_RESTART_OK
```
