# Phase 41.1 - Dynamic Layout Smoke Fix

- Updates legacy Nexus smoke validation to accept the new dynamic `device_visual.html` include path.
- Updates MikroTik topology smoke validation to avoid noisy management-command output and validate real device/group data.
- Adds finalization script to run checks, collect static files, and restart the Waitress task.
