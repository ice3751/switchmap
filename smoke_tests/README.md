# SwitchMap Smoke Tests

Smoke tests are grouped by expected behavior:

- `current`: active regression checks that should pass on the current UI and access-control model.
- `production`: deployment-oriented checks that run with production-like environment overrides.
- `legacy`: older phase checks kept for historical context. These may fail because they target pre-login routes or superseded CSS/UI markers.

Run the active suite:

```powershell
venv\Scripts\python.exe smoke_tests\run_smoke.py current
```

Run the production suite:

```powershell
venv\Scripts\python.exe smoke_tests\run_smoke.py production
```

