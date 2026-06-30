# Phase 60.1 - Legacy compatibility marker fix

Fixes compatibility markers required by previous MikroTik smoke tests after the Phase 60 dashboard redesign.

Changes:
- Restores hidden legacy markers in `mikrotik_center.html`.
- Keeps the Phase 60 monitoring dashboard UI unchanged.
- Adds a small ASCII-safe compatibility smoke test.

No migration, no database change, no RouterOS change, no credential storage.
