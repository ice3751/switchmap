# Phase 78.1 - Alarm Cleanup Badge UI

Scope: UI-only fix for Phase78 Alarm Cleanup Active Alarms card.

Changed:
- Replaced mixed RTL/LTR text `Critical / Warning` with two isolated badges.
- Added CSS isolation with `direction:ltr` and `unicode-bidi:isolate`.

Not changed:
- Alarm logic
- Recheck
- Resolve stale
- Database
- Dashboard
- SSH
- Popup
- Quick Search
- Topology
