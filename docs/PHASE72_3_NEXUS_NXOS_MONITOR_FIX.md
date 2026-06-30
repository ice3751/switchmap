# Phase 72.3 - Nexus NX-OS SFP/CRC Monitor Fix

- Fixes Nexus SFP/CRC background monitor command profile.
- Catalyst keeps IOS command profile.
- Nexus uses NX-OS command profile:
  - show interface status
  - show interface counters errors
  - show interface transceiver details
- No UI, DB schema, credentials, or scheduled task changes.
- Uses existing Cisco DPAPI credential.
