# SwitchMap Smoke Tests — Phase94R3 Baseline

This folder contains the active read-only verification runner for the live SwitchMap baseline.

Safety constraints:

- no visible test devices
- no database mutation
- no SSH/SNMP execution
- no backup write
- no restore execution
- no service restart
- no Scheduled Task modification

Run from `C:\SwitchMap`:

```cmd
venv\Scripts\python.exe smoke_tests\run_smoke.py --strict
```

The runner writes reports to `logs` only.
