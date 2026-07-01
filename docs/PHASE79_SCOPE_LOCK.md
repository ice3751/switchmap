# Phase79 Scope Lock

Phase79 must be implemented in guarded sub-phases.

Stable functions that must not break:

- Dashboard
- Quick Search
- Switch Map rendering
- Port Popup
- Existing single SSH action
- Bulk SSH
- Alarm Center
- Phase78 Alarm Cleanup
- SFP Monitor
- Topology
- Backup Center
- Login / Roles

Requested Phase79 features:

1. Multi SSH actions for one port.
2. Refresh the same port after SSH execution.
3. Alarm filters.
4. Port disconnect history / last connected device visible from port click.

Execution order:

1. Phase79.0 Preflight Guard - read-only, no app changes.
2. Phase79.1 Port Connection History model + collector only.
3. Phase79.2 Popup display for Last Connected Device.
4. Phase79.3 Safe post-SSH port refresh verification.
5. Phase79.4 Multi SSH Action UI + backend, additive only.
6. Phase79.5 Alarm filters.
7. Phase79.6 Full regression verify.

Rules:

- No password storage.
- View Only must never execute SSH or resolve/modify alarms.
- Operator/Admin only for operational changes.
- Every risky step needs backup, expected result, risk, and rollback.
- UI work must not redesign Dashboard layout.
- Search must not re-render ports.
