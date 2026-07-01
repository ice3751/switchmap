Phase98-100 Final Refine / Safety / Release Lock

Scope:
- Canonical cleanup of inventory/alarm_policy.py without changing characterized behavior.
- Restore candidate validation safety hardening in inventory/views.py.
- Final release-lock verification command.
- No DB mutation, no migration write, no service restart, no SSH, no restore execution, no backup write, no visible test data.

Run:
cd /d C:\SwitchMap
scripts\98_100_phase98_100_final_refine_release_lock.cmd
