# Phase 40 - MikroTik Inventory and Topology Classification

## Scope
- Add device classification fields to Switch.
- Add MikroTik device families and roles.
- Seed known MikroTik devices from Winbox inventory without storing credentials.
- Show MikroTik devices as a separate visual card instead of Cisco 3850/Nexus SVG.
- Group MikroTik routers, core switch, remote offices and APs in Topology.

## No credential storage
Only name, IP, Winbox port, role, site and model are saved. Username/password from Winbox export are not used.

## Apply
```cmd
cd /d C:\SwitchMap
scripts\12_phase40_mikrotik_inventory.cmd
```

## Rollback
Restore the project backup taken before applying this package, or revert these files and migration.
