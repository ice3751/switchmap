# Phase 72.2 - Split Vendor SSH Credentials

- Cisco credentials are stored separately from MikroTik credentials.
- Cisco SFP/CRC background monitor uses only the Cisco profile.
- Existing legacy Cisco credential remains readable for compatibility.
- MikroTik credential is stored for MikroTik-specific SSH monitoring/tests and is not used by Cisco SFP/CRC monitor.
- Passwords are protected by Windows Current User DPAPI and are not stored in SQLite.
