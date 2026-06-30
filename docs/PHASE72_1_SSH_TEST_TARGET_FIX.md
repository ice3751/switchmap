Phase 72.1

Fixes SSH credential test target selection.

The credential test no longer selects MikroTik/non-Cisco devices such as AX3-Karaj.
It tests only active, SSH-enabled, operational Cisco/Nexus/Catalyst switches.
No database, UI, static, template, or scheduled task settings are changed.
