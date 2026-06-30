Phase102 - SwitchMap Brand Header / Favicon / Menu Icons

Scope:
- Add final SwitchMap brand assets under inventory/static/inventory/brand/phase102.
- Add favicon and header brand icon.
- Add navigation/menu icon CSS with one dedicated SVG per target menu item.
- Sync phase102 static files into staticfiles if the directory exists.
- Restart SwitchMap Waitress only after all verification steps pass.

Safety:
- No DB mutation
- No migration
- No restore enablement
- No SSH execution
- No backup write
- No visible test data
- Auto rollback on apply or verify failure

Run:
cd /d C:\SwitchMap
scripts\102_phase102_brand_icons.cmd
