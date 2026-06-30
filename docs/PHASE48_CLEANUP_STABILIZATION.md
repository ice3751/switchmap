# SwitchMap Phase 48 - Cleanup and Stabilization

## Scope

Phase 48 is a non-visual stabilization phase after the safe UI changes from phases 43-47.

## Changed files

- `smoke_tests/manifest.json`
- `smoke_tests/switchmap_48_cleanup_stabilization_smoke_test.py`
- `scripts/24_phase48_cleanup_stabilization.cmd`
- `docs/PHASE48_CLEANUP_STABILIZATION.md`
- `README_PHASE48_APPLY.txt`

## Not changed

- No model changes
- No migration changes
- No database changes
- No environment file changes
- No settings changes
- No SSH backend changes
- No device layout backend changes

## Purpose

- Make the smoke-test manifest match the current real files.
- Add a focused phase 48 stabilization smoke test.
- Verify that phase 43-47 UI markers are still present.
- Verify that the static CSS file exists both under `inventory/static` and `staticfiles`.
- Block accidental risky phase files such as migrations or environment overrides.

## Validation

Run:

```cmd
cd /d C:\SwitchMap
venv\Scripts\activate
python smoke_tests\switchmap_48_cleanup_stabilization_smoke_test.py
python smoke_tests\run_smoke.py current
python manage.py check
```

Expected result:

```text
SwitchMap phase 48 cleanup stabilization smoke test: OK
SUMMARY 2 pass 0 fail
System check identified no issues (0 silenced).
```

## Rollback

Restore these files from the previous project ZIP:

- `smoke_tests/manifest.json`

Then remove these files if needed:

- `smoke_tests/switchmap_48_cleanup_stabilization_smoke_test.py`
- `scripts/24_phase48_cleanup_stabilization.cmd`
- `docs/PHASE48_CLEANUP_STABILIZATION.md`
- `README_PHASE48_APPLY.txt`
